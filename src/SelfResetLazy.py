from threading import Semaphore, Timer
from typing import Callable, TypeVar, Generic, Any


T = TypeVar('T')



class SelfResetLazy(Generic[T]):
    def __init__(self, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any], resetAfter: float) -> None:
        self._val: T = None
        self._has_val = False
        self._semaphore = Semaphore(1)

        self.fnCreateVal = fnCreateVal
        self.fnDestroyVal = fnDestroyVal
        self.resetAfter = resetAfter
        self._timer: Timer = None
    
    def unsetValue(self):
        try:
            self._semaphore.acquire()
            if self._has_val:
                self.fnDestroyVal(self._val) # Pass in the current value
                self._val = None
                self._has_val = False
                self._setTimer()
        finally:
            self._semaphore.release()

        return self

    
    def _setTimer(self):
        self._timer = Timer(interval=self.resetAfter, function=self.unsetValue)
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
