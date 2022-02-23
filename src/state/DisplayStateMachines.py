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
from time import sleep
from threading import Semaphore



class ePaperStateMachine(StateManager):
    
    def __init__(self, config):
        super().__init__(config=config, stateConfig=config['state_managers']['epaper'])
        self._config = config
        # Used to synchronize state activations, as they are long-running and expensive
        self._busy = False
        self._semaphore = Semaphore(1)
    
    @property
    def busy(self) -> bool:
        return self._busy

    def finalize(self, state_to: str, state_from: str, transition: str, **kwargs):
        self._busy = True
        self._semaphore.acquire()
        # activating a state means to display its rendered images on the e-paper.
        # This happens outside of this application, and we rely on the images
        # being present at this point.
        # If we also use an LCD, we may also show some info there.
        data_folder = self._config['general']['data_folder'][os.name]

        fp_black = None
        fp_red = None
        try:
            fp_black = open(file=abspath(join(data_folder, f'{state_to}_b.png')), mode='rb')
            fp_red = open(file=abspath(join(data_folder, f'{state_to}_r.png')), mode='rb')
            
            blackimg = Image.open(fp=fp_black)
            redimg = Image.open(fp=fp_red)

            # Now the following will take approx ~15-30 seconds. We will therefore
            # repeatedly trigger the progress event.
            def progress():
                n = 90
                for i in range(1, n+1):
                    self.logger.debug('Event: activateProgress')
                    self.activateProgress(sm=self, progress=i/n)
                    sleep(30/float(n)) # We assume 30 seconds

            self._tpe.submit(progress)

            ePaper.display(black_img=blackimg, red_img=redimg)
            self._state = state_to
        finally:
            if not fp_black is None and not fp_black.closed:
                fp_black.close()
            if not fp_red is None and not fp_red.closed:
                fp_red.close()

        # Before releasing, wait a few seconds so it won't be triggered too often.
        sleep(3)
        self._semaphore.release()
        self._busy = False
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
                self._apps['show-progress'] = Progress(
                    lcd=self._lcd, strFn=lambda: 'Loading',
                    show_percent='percent' in args['indicator'], num_dots=2 if 'dots' in args['indicator'] else 0)
            elif transition['name'] == 'show-datetime':
                self._apps['show-datetime'] = Datetime(lcd=self._lcd, mode=args['mode'], l1interval=args['line1_timer'], l2interval=args['line2_timer'])
    
    def getApp(self, name: str) -> LcdApp:
        if name in self._apps.keys():
            return self._apps[name]
        raise Exception(f'No app with name "{name}" registered.')

    def finalize(self, state_to: str, state_from: str, transition: str, **kwargs):
        """
        Here we'll just activate the correct app.
        """
        for app in self._apps.values():
            app.stop()
        
        # Should we have a progress app, reset its progress.
        if 'show-progress' in self._apps.keys():
            self._apps['show-progress'].progress(0.0)

        if transition in self._apps.keys():
            self._apps[transition].start()
        
        return self