from threading import Timer, Semaphore
from abc import ABC, abstractmethod
from events import Events
from src.CustomFormatter import CustomFormatter
from concurrent.futures import ThreadPoolExecutor


class StateManager(ABC, Events):

    def __init__(self, config, stateConfig):
        Events.__init__(self=self, events=('beforeInit', 'activateProgress', 'afterFinalize'))
        self._config = config
        self._stateConfig = stateConfig
        self._state: str = None
        self._timer: Timer = None
        self._semaphore = Semaphore(1)
        # Used to asynchronously fire events
        self._tpe = ThreadPoolExecutor(max_workers=1)
        self.logger = CustomFormatter.getLoggerFor(name=self.__class__.__name__)
    
    def __del__(self):
        self._unsetTimer()
        self._tpe.shutdown()
    
    @property
    def state(self):
        return self._state

    def _unsetTimer(self):
        if type(self._timer) is Timer and self._timer.is_alive():
            self._timer.cancel()
        return self

    
    def _setTimer(self, timeout: float):
        self._unsetTimer()
        self._timer = Timer(interval=timeout, function=lambda: self.activate(transition='timer'))
        self._timer.start()
        return self
    
    def _initState(self, state_to: str, state_from: str=None, transition: str=None, **kwargs):
        self.logger.debug(f'Firing event: beforeInit, before initializing state "{state_to}".')
        self._tpe.submit(lambda: self.beforeInit(sm=self, state_from=state_from, state_to=state_to, transition=transition, **kwargs))

        self._unsetTimer()

        # Now wait for the user implementation (init logic of the transition-into state):
        self.logger.debug(f'Attempting finalization of state: "{state_to}".')
        try:
            self._finalize(state_from=state_from, transition=transition, state_to=state_to, **kwargs)
            # Now if this was successful, replace the current state:
            self._state = state_to

            # Futhermore, activating means to initialize all transitions out of this
            # state. There may be zero or one 'timer'-type transition, and arbitrary
            # many user transitions. A pending timer-transition gets cancelled if
            # another transition gets called in the meantime. A user-transition
            # (type=external) is called from outside, with the target state's name.
            timer_trans = list(filter(lambda t: t['type']=='timer' and t['from']==self.state, self._stateConfig['transitions']))
            if len(timer_trans) > 1:
                raise Exception(f'More than one timer-transition is defined for state "{state_to}".')
            if len(timer_trans) == 1:
                tt = timer_trans[0]
                tt_timeout = float(tt['args']['timeout'])
                if 'duration' in kwargs:
                    # Allow override:
                    self.logger.debug(f'Overriding timeout from {format(tt_timeout, ".2f")} seconds to {format(kwargs["duration"], ".2f")} seconds.')
                    tt_timeout = float(kwargs['duration'])
                self.logger.debug(f'Setting timer for transition into state "{tt["to"]}" after {format(tt_timeout, ".2f")} seconds.')
                self._setTimer(timeout=tt_timeout)
            
            self.logger.debug(f'Firing event: afterFinalize, after finalization of state "{state_to}".')
            self._tpe.submit(lambda: self.afterFinalize(sm=self, state_from=state_from, state_to=state_to, transition=transition))
        except Exception as e:
            self.logger.error(f'Exception occurred, cannot finalize state "{state_to}": {str(e)}')
            raise e # re-throw; 'finally' will still be run
        
        self.logger.debug(f'Finalization complete for: "{state_to}".')

        return self
    
    def init(self):
        """
        Transitions this state machine from an uninitialized state into
        its defined initial state.
        """
        return self.activate(transition=None)
    
    def availableTransitions(self):
        def atFilter(t: dict):
            if t['from'] == self.state or t['from'] == '*':
                if self.state == t['to'] and 'allow-reentry' in t.keys() and not t['allow-reentry']:
                    # Wants to go from A -> A, which is allowed by default, but NOT here:
                    return False
                return True
            return False
        
        return list(filter(atFilter, self._stateConfig['transitions']))
    
    def activate(self, transition: str=None, **trans_args):
        """
        This method is supposed to be called by the user, in order to start (or
        activate) a transition by name.
        It is a synchronized method, such that is is not possible to active the
        same transition more than once.
        """
        try:
            self._semaphore.acquire()
            if not type(transition) is str:
                if type(self._state) is str:
                    raise Exception(f'"transition" may only be None if activating the initial state.')
                return self._initState(state_to=self._stateConfig['initial'])

            # Let's check if the current state has the requested transition:
            transitions = list(filter(lambda t: (t['from']==self.state or t['from']=='*') and t['name']==transition, self._stateConfig['transitions']))
            if len(transitions) == 0:
                raise Exception('The current state "{self._state}" has no transition "{transition}".')
            elif len(transitions) > 1:
                raise Exception('The current state "{self._state}" has more than one transition with the name "{transition}".')

            trans = transitions[0]
            args = {}
            if 'args' in trans:
                args = trans['args']
            # Merge with given args, which have precedence!
            args = args | trans_args
            return self._initState(
                state_from=trans['from'], transition=trans['name'], state_to=trans['to'], **args)
        finally:
            self._semaphore.release()

    @abstractmethod
    def _finalize(self, state_to: str, state_from: str=None, transition: str=None, **kwargs):
        """
        This method is the user implementation of what exactly happens once the
        state machine acknowledges the transition into a new state.
        """
        pass
