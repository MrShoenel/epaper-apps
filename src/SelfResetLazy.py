from concurrent.futures import Future
from threading import Semaphore, Timer, Thread
from typing import Callable, TypeVar, Generic, Any, Union
from timeit import default_timer as timer
from src.CustomFormatter import CustomFormatter
from queue import Queue


T = TypeVar('T')



class SelfResetLazy(Generic[T]):
    def __init__(self, resource_name: str, fnCreateVal: Callable[[], T], fnDestroyVal: Callable[[T], Any]=None, resetAfter: float=None) -> None:
        self.resource_name = resource_name
        self._val: T = None
        self._has_val = False
        self._semaphore = Semaphore(1)

        self._fnCreateVal = fnCreateVal
        self._fnDestroyVal = fnDestroyVal
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
                if callable(self._fnDestroyVal):
                    self.logger.debug(f'Attempting to destroy the value by calling "fnDestroyVal()".')
                    self._fnDestroyVal(self._val) # Pass in the current value
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
    def hasValueVolatile(self) -> bool:
        return self._has_val

    @property
    def hasValue(self) -> bool:
        try:
            self._semaphore.acquire()
            return self._has_val
        finally:
            self._semaphore.release()

    def valueVolatile(self) -> Union[None, T]:
        return self._val

    @property
    def value(self) -> T:
        try:
            self._semaphore.acquire()
            if not self._has_val:
                start = timer()
                self.logger.debug(f'Calling "fnCreateVal()" to lazily produce value.')
                self._val = self._fnCreateVal()
                self._has_val = True
                self.logger.debug(f'"fnCreateVal()" took {format(timer() - start, ".2f")} seconds to produce a value.')
                self._setTimer()
            return self._val
        except Exception as e:
            self.logger.error(f'Cannot lazily produce value. Exception was: {str(e)}')
            raise e
        finally:
            self._semaphore.release()

    @property
    def valueFuture(self) -> Future[T]:
        f = Future()

        def setVal():
            try:
                f.set_result(self.value)
            except Exception as e:
                f.set_exception(e)

        temp = self._val
        if type(temp) is T and self.hasValueVolatile:
            f.set_result(temp)
        else:
            Thread(target=setVal).start()

        return f



class AtomicResource(Generic[T]):
    def __init__(self, resource_name: str=None, item: T=None) -> None:
        self._queue = Queue(maxsize=1)
        self.resource_name = resource_name

        self.logger = CustomFormatter.getLoggerFor(
            f'{self.__class__.__name__}({resource_name})')

        if not item is None:
            self.recover(item)

    @property
    def available(self):
        return self._queue.full()

    @property
    def busy(self):
        return self._queue.empty()

    def obtain(self) -> T:
        # Block until available.
        self.logger.debug('Attempt to obtain item.')
        item = self._queue.get(block=True, timeout=None)
        self.logger.debug('Obtained item.')
        return item

    def recover(self, item: T):
        # This'll throw if queue not empty.
        # Momentarily, we don't care if the recovered item is the same as was obtained.
        self._queue.put_nowait(item=item)
        self.logger.debug('Recovered item.')
        return self
