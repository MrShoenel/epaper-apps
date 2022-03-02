from src.state.StateManager import StateManager
from src.ePaper import ePaper
from src.lcd.TextLCD import TextLCD
from PIL import Image
import os
from os.path import abspath, join
from typing import Dict
from src.lcd.apps.LcdApp import LcdApp
from src.lcd.apps.Datetime import Datetime
from src.lcd.apps.Progress import Progress
from collections import deque
from typing import Dict
from statistics import mean
from timeit import default_timer as timer
from time import sleep
from threading import Semaphore
from fasteners import InterProcessLock



class ePaperStateMachine(StateManager):
    
    def __init__(self, config):
        super().__init__(config=config, stateConfig=config['state_managers']['epaper'])
        self._config = config
        self._retries = self._stateConfig['retries']['num']
        self._retry_delay = self._stateConfig['retries']['delay']
        # Used to synchronize state activations, as they are long-running and expensive
        self._busy = False
        self._semaphore_finalize = Semaphore(1)
        self._last_durations: Dict[str, deque] = {}
    
    @property
    def busy(self) -> bool:
        return self._busy

    def lastDuration(self, state_to: str, with_clear: bool) -> float:
        q = self._last_durations[f'{state_to}_{with_clear}']
        if len(q) == 0:
            return 30.0 # The default duration if we don't know so far
        return mean(list(q))

    def _finalize(self, state_to: str, state_from: str, transition: str, **kwargs):
        self._busy = True
        self._semaphore_finalize.acquire()
        # activating a state means to display its rendered images on the e-paper.
        # This happens outside of this application, and we rely on the images
        # being present at this point.
        # If we also use an LCD, we may also show some info there.
        data_folder = self._config['general']['data_folder'][os.name]

        # kwargs will be the arguments from the transition.
        clear = 'timeout' in kwargs # was a timer-type transition


        if not f'{state_to}_{clear}' in self._last_durations.keys():
            # 3 is enough to more quickly react to recent changes.
            self._last_durations[f'{state_to}_{clear}'] = deque(maxlen=3)

        fp_black = None
        fp_red = None
        try:
            lock = InterProcessLock(path=abspath(join(data_folder, 'write.lock')))
            lock.acquire()

            fp_black = open(file=abspath(join(data_folder, f'{state_to}_b.png')), mode='rb')
            fp_red = open(file=abspath(join(data_folder, f'{state_to}_r.png')), mode='rb')
            
            blackimg = Image.open(fp=fp_black)
            redimg = Image.open(fp=fp_red)

            # Now the following will take approx ~15-45 seconds. We will therefore
            # repeatedly trigger the progress event.
            done = False
            def progress():
                num_updates = 100
                wait_total = self.lastDuration(state_to=state_to, with_clear=clear)
                wait_frac = wait_total / num_updates
                start = timer()

                while True:
                    progress = min((timer() - start) / wait_total, 1.0)
                    if done or progress >= 1.0:
                        self.activateProgress(sm=self, state_from=state_from, state_to=state_to, transition=transition, progress=1.0)
                        break
                    self.activateProgress(sm=self, state_from=state_from, state_to=state_to, transition=transition, progress=progress)
                    sleep(wait_frac)

            self._tpe.submit(progress)
            self.logger.debug('Writing black and red image to e-paper.')

            retries = self._retries
            while retries >= 0:
                try:
                    start_write = timer()
                    ePaper.display(black_img=blackimg, red_img=redimg, clear_before=clear)

                    duration = timer() - start_write
                    self._last_durations[f'{state_to}_{clear}'].append(duration)
                    self.logger.debug(f'Writing took {format(duration, ".2f")} seconds.')
                    self._state = state_to
                    break
                except Exception as e:
                    retries -= 1
                    if retries < 0:
                        self.logger.error(f'ePaper::display finally errored after {self._retries + 1} attempt(s) to display an image. The exception was: {str(e)}')
                        raise e # re-throw
                    self.logger.debug(f'ePaper::display had an exception, trying again in {format(self._retry_delay, ".2f")} seconds ({retries+1} retries left). Exception was: {str(e)}')
                    sleep(self._retry_delay)
                finally:
                    done = True
        finally:
            if not fp_black is None and not fp_black.closed:
                fp_black.close()
            if not fp_red is None and not fp_red.closed:
                fp_red.close()
            lock.release()
            self._semaphore_finalize.release()
            self._busy = False

        # Before releasing, wait a few seconds so it won't be triggered too often.
        sleep(3.0)
        return self


class TextLcdStateMachine(StateManager):

    def __init__(self, config):
        super().__init__(config=config, stateConfig=config['state_managers']['textlcd'])
        self._config = config
        self._lcd = TextLCD()

        # The LCD state machine works a bit differently, in that we have a couple
        # of target states that we can transition into, no matter where we're coming
        # from. Since the LCD display something lively in those states, we have mini-
        # "apps" that are activated once we get there.
        self._apps: Dict[str, LcdApp] = {}

        for transition in self._stateConfig['transitions']:
            args = transition['args']
            if transition['name'] == 'show-progress':
                self._apps[transition['name']] = Progress(
                    lcd=self._lcd, strFn=lambda: 'Loading',
                    show_percent='percent' in args['indicator'], num_dots=3 if 'dots' in args['indicator'] else 0)
            elif transition['name'] == 'show-datetime':
                self._apps[transition['name']] = Datetime(lcd=self._lcd, mode=args['mode'], l1interval=args['line1_timer'], l2interval=args['line2_timer'], l1every=args['line1_every'], l2every=args['line2_every'])
    
    def getApp(self, name: str) -> LcdApp:
        if name in self._apps.keys():
            return self._apps[name]
        raise Exception(f'No app with name "{name}" registered.')

    def _finalize(self, state_to: str, state_from: str, transition: str, **kwargs):
        """
        Here we'll just activate the correct app.
        """
        self.logger.debug('Stopping all apps.')
        for app in self._apps.values():
            app.stop()
            app.reset() # Return app to initial state (if any)

        if transition in self._apps.keys():
            self.logger.debug(f'Starting app: {transition}')
            self._apps[transition].start()
        
        return self
