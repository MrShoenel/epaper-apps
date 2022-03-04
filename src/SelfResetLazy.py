from threading import Semaphore, Timer
from typing import Callable, TypeVar, Generic, Any
from timeit import default_timer as timer
from src.CustomFormatter import CustomFormatter
from events import Events


T = TypeVar('T')



class SelfResetLazy(Generic[T], Events):
    def __init__(self, resource_name: str, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any]=None, resetAfter: float=None) -> None:
        Events.__init__(self=self, events=('beforeUnset',))
        self.resource_name = resource_name
        self._val: T = None
        self._has_val = False
        self._semaphore = Semaphore(1)

        self.fnCreateVal = fnCreateVal
        self.fnDestroyVal = fnDestroyVal
        self._resetAfter = resetAfter
        self._timer: Timer = None

        self.logger = CustomFormatter.getLoggerFor(
            f'{self.__class__.__name__}({resource_name})')
    
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
            self.logger.debug('Triggering "beforeUnset" synchronously.')
            self.beforeUnset(self)
        except Exception as e:
            if handle_ex:
                self.logger.error(f'Triggering event "beforeUnset" caused an exception: {str(e)}')
            else:
                raise e

        try:
            self._semaphore.acquire()
            if self._has_val:
                if callable(self.fnDestroyVal):
                    self.logger.debug(f'Attempting to destroy the value by calling "fnDestroyVal()".')
                    self.fnDestroyVal(self._val) # Pass in the current value
                self._val = None
                self._has_val = False
        except Exception as e:
            if handle_ex:
                self.logger.error(f'Unsetting the value using "fnDestroyVal()" caused an exception: {str(e)}')
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
            self.logger.debug(f'Setting timer for automatic destruction of value after {format(self._resetAfter, ".2f")} seconds.')
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
                start = timer()
                self.logger.debug(f'Calling "fnCreateVal()" to lazily produce value.')
                self._val = self.fnCreateVal()
                self._has_val = True
                self.logger.debug(f'"fnCreateVal()" took {format(timer() - start, ".2f")} seconds to produce a value.')
                self._setTimer()
            return self._val
        except Exception as e:
            self.logger.error(f'Cannot lazily produce value. Exception was: {str(e)}')
            raise e
        finally:
            self._semaphore.release()
