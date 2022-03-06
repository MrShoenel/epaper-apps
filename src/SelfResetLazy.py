from threading import Semaphore, Timer
from typing import Callable, TypeVar, Generic, Any
from timeit import default_timer as timer
from src.CustomFormatter import CustomFormatter


T = TypeVar('T')



class SelfResetLazy(Generic[T]):
    def __init__(self, resource_name: str, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any]=None, resetAfter: float=None) -> None:
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


class LazyResource(SelfResetLazy):
    def __init__(self, resource_name: str, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any] = None, resetAfter: float = None) -> None:
        super().__init__(resource_name, fnCreateVal, fnDestroyVal, resetAfter)
        self._semaphoreRes = Semaphore(value=0)
        self._semaphoreSync = Semaphore(value=1)
    
    @property
    def available(self) -> bool:
        try:
            self._semaphoreSync.acquire()
            return self._semaphoreRes._value == 1
        finally:
            self._semaphoreSync.release()
    
    @property
    def busy(self) -> bool:
        try:
            self._semaphoreSync.acquire()
            return self._semaphoreRes._value == 0
        finally:
            self._semaphoreSync.release()


    def obtain(self) -> T:
        try:
            self._semaphoreSync.acquire()

            had_value = self._has_val

            val = super().value
            if not had_value:
                # Increase as a new initial value was just produced!
                self._semaphoreRes.release()

            self._semaphoreRes.acquire()
            self.logger.debug('Obtained value.')
            return val
        finally:
            self._semaphoreSync.release()
    
    def recover(self, resource: T):
        try:
            self._semaphoreSync.acquire()

            if self._semaphoreRes._value == 1:
                raise Exception('The resource was not previously obtained, not sure what you are trying to return.')

            if not self._has_val:
                raise Exception('You cannot return a value that was not previously obtained.')

            if not super().value is resource:
                raise Exception('You must return the same value that was previously obtained.')

            self.logger.debug('Recovered value.')
            self._semaphoreRes.release()
            return self
        finally:
            self._semaphoreSync.release()

    def unsetValue(self, handle_ex: bool = True):
        try:
            self._semaphoreSync.acquire()

            if self.hasValue:
                # Reduce count in semaphore to 0:
                self._semaphoreRes.acquire()
            return super().unsetValue(handle_ex)
        finally:
            self._semaphoreSync.release()

    @property
    def value(self) -> T:
        self.logger.warn(f'In {self.__class__.__name__} use obtain() and recover() to manage the resource. Forwarding this call now to obtain().')
        return self.obtain()
