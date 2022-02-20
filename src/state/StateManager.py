import os
from os.path import abspath, join
from pathlib import 
from threading import Timer
from src.ePaper import ePaper
from PIL import Image


class StateManager:
    def __init__(self, config):
        self._config = config
        self._stateConfig = config['state_manager']
        self._state: str = None
        self._epaper = ePaper()
        self._timer: Timer = None
    
    @property
    def state(self):
        return self._state

    def _unsetTimer(self):
        if type(self._timer) is Timer:
            self._timer.cancel()
            del self._timer
        return self

    
    def _setTimer(self, timeout: float):
        self._unsetTimer()
        self._timer = Timer(interval=timeout, function=lambda: self.activate(transition='timer'))
        return self
    
    def _initState(self, state: str):
        c = self._stateConfig
        # 'state' must be one of the defined views.
        if not state in c['views'].keys():
            raise Exception(f'The state "{state}" is not defined.')

        self._unsetTimer()

        # to 'init' a state means to display its rendered images on the e-paper.
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
        
        self._epaper.display(black_img=blackimg, red_img=redimg)
        self._state = state

        # Futhermore, activating means to initialize all transitions out of this
        # state. There may be zero or one 'timer'-type transition, and arbitrary
        # many user transitions. A pending timer-transition gets cancelled if
        # another transition gets called in the meantime. A user-transition
        # (type=external) is called from outside, with the target state's name.
        timer_trans = list(filter(function=lambda t: t.type=='timer', iterable=self._stateConfig['transitions']))
        if len(timer_trans) > 1:
            raise Exception('More than one timer-transition is defined for state "{state}".')
        if len(timer_trans) == 1:
            tt = timer_trans[0]
            self._setTimer(timeout=float(tt['args']['timeout']))

        return self
    
    def init(self):
        """
        Transitions this state machine from an uninitialized state into
        its defined initial state.
        """
        return self.activate(transition=None)
    
    def activate(self, transition: str=None):
        if not type(transition) is str:
            if type(self._state) is str:
                raise Exception(f'"transition" may only be None if activating the initial state.')
            return self._initState(state=self._stateConfig['initial'])

        # Let's check if the current state has the requested transition:
        transitions = list(filter(function=lambda t: t.from==self._state and t.name==transition, iterable=self._stateConfig['transitions']))
        if len(transitions) == 0:
            raise Exception('The current state "{self._state}" has no transition "{transition}".')
        elif len(transition) > 1:
            raise Exception('The current state "{self._state}" has more than one transition with the name "{transition}".')

        return self._initState(state=transitions[0].to)
