from src.state.StateManager import StateManager
from src.ePaper import ePaper
from src.lcd.TextLCD import TextLCD
from typing import Dict
from src.lcd.apps.LcdApp import LcdApp
from src.lcd.apps.Datetime import Datetime
from src.lcd.apps.Progress import Progress
from asyncio import run, sleep



class ePaperStateMachine(StateManager):
    
    def __init__(self, config):
        super.__init__(stateConfig=config['state_managers']['epaper'])
        self._config = config
        self._epaper = ePaper()

    async def finalize(self, state_from: str, transition: str, state_to: str, **kwargs):
        # activating a state means to display its rendered images on the e-paper.
        # This happens outside of this application, and we rely on the images
        # being present at this point.
        # If we also use an LCD, we may also show some info there.
        data_folder = self._config['general']['data_folder'][os.name]
        
        blackimg = None
        redimg = None
        with open(file=abspath(join(data_folder, f'{state}_b.png')) as fp:
            blackimg = Image.open(fp=fp)
        with open(file=abspath(join(data_folder, f'{state}_r.png')) as fp:
            redimg = Image.open(fp=fp)

        # Now the following will take approx ~15-20 seconds. We will therefore
        # repeatedly trigger the progress event.
        async def progress():
            n = 40 # number of updates, ~2.5% steps
            for i in range(1, n+1):
                self.activateProgress(sm=self, progress=float(i)/float(n))
                await sleep(float(n)/float(15)) # We assume 15 seconds for now..
        
        progress_fut = progress()
        
        self._epaper.display(black_img=blackimg, red_img=redimg)
        self._state = state

        await progress_fut

        return self


class TextLcdStateMachine(StateManager):

    def __init__(self, config):
        super.__init__(stateConfig=config['state_managers']['textlcd'])
        self._config = config
        self._lcd = TextLCD()

        # The LCD state machine works a bit differently, in that we have a couple
        # of target states that we can transition into, no matter where we're coming
        # from. Since the LCD display something lively in those states, we have mini-
        # "apps" that are activated once we get there.
        self._apps: Dict[str, LcdApp]

        for transition in self._stateConfig['transitions'].values():
            args = transition['args']
            if transition.name == 'show-progress':
                self._apps['show-progress'] = Progress(lcd=self._lcd, strFn=lambda: 'Loading', show_percent='percent' in args, show_dots='dots' in args)
            elif transition.name == 'show-datetime':
                self._apps['show-datetime'] = Datetime(lcd=self._lcd, mode=args['mode'], l1interval=args['line1_timer'], l2interval=args['line2_timer'])
    
    def getApp(self, name: str) -> LcdApp:
        if name in self._apps.keys():
            return self[name]
        raise Exception(f'No app with name "{name}" registered.')

    async def finalize(self, state_from: str, transition: str, state_to: str, **kwargs):
        """
        Here we'll just activate the correct app.
        """
        for app in self._apps.values():
            app.stop()

        if transition in self._apps.keys():
            self._apps[transition].start()
        
        return self