import imp
from fasteners import InterProcessLock
from threading import Semaphore


class SuperLock(InterProcessLock):

    def __init__(self, path, sleep_func=..., logger=None):
        super().__init__(path, sleep_func, logger)
        self._semaphore = Semaphore(1)
    

    def acquire(self, blocking=True, delay=..., max_delay=..., timeout=None):
        temp = super().acquire(blocking, delay, max_delay, timeout)
        if temp:
            if self._semaphore.acquire(blocking=blocking, timeout=timeout):
                return True
            else:
                super().release()
        return False
    
    def release(self):
        self._semaphore.release()
        super().release()
