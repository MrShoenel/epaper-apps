from threading import Semaphore, Timer
from typing import Callable, TypeVar, Generic, Any
from src.CustomFormatter import CustomFormatter


T = TypeVar('T')



class SelfResetLazy(Generic[T]):
    def __init__(self, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any]=None, resetAfter: float=None) -> None:
        self._val: T = None
        self._has_val = False
        self._semaphore = Semaphore(1)

        self.fnCreateVal = fnCreateVal
        self.fnDestroyVal = fnDestroyVal
        self._resetAfter = resetAfter
        self._timer: Timer = None

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    @property
    def resetAfter(self):
        try:
            self._semaphore.acquire()
            return self._resetAfter
        finally:
            self._semaphore.release()
    
    @resetAfter.setter
    def resetAfter(self, value: float=None):
        try:
            self._semaphore.acquire()
            self._resetAfter = value
            self._setTimer() # Conditionally re-sets a timer
        finally:
            self._semaphore.release()
        
        return self
    
    def unsetValue(self, handle_ex: bool=True):
        try:
            self._semaphore.acquire()
            if self._has_val:
                if callable(self.fnDestroyVal):
                    self.fnDestroyVal(self._val) # Pass in the current value
                self._val = None
                self._has_val = False
        except Exception as e:
            if handle_ex:
                self.logger.error(f'Unsetting the value caused an exception: {str(e)}')
            else:
                raise e
        finally:
            self._semaphore.release()

        return self
    
    def _setTimer(self):
        if type(self._timer) is Timer and self._timer.is_alive():
            self._timer.cancel()
            self._timer = None

        if type(self._resetAfter) is float and self._resetAfter > 0.0:
            self._timer = Timer(interval=self._resetAfter, function=self.unsetValue)
            self._timer.start()
        return self
    
    @property
    def hasValue(self) -> bool:
        try:
            self._semaphore.acquire()
            return self._has_val
        finally:
            self._semaphore.release()
    
    @property
    def value(self) -> T:
        try:
            self._semaphore.acquire()
            if not self._has_val:
                self._val = self.fnCreateVal()
                self._has_val = True
                self._setTimer()
            return self._val
        finally:
            self._semaphore.release()
