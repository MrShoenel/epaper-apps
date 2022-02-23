from src.lcd.apps.LcdApp import LcdApp
from src.lcd.TextLCD import TextLCD
from threading import Timer, Semaphore
from typing import Callable
from src.lcd.ProgressString import ProgressString
from src.CustomFormatter import CustomFormatter



class Progress(LcdApp):
    def __init__(self, lcd: TextLCD, strFn: Callable[[], str], show_percent: bool=True, num_dots: int=3):
        self._lcd = lcd
        self.strFn = strFn
        self.show_percent = show_percent
        self.num_dots = num_dots
        # To synchronize updating both LCD's lines
        self._semaphore = Semaphore(1)
        self._ps = ProgressString(strFn=strFn, num_dots=num_dots)
        self._activateTimers = False
        self._timer: Timer = None
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

    def progress(self, value: float):
        self._semaphore.acquire()
        if value < 0.0 or value > 1.0:
            raise Exception('progress must be in [0.0, 1.0].')
        self._ps.progress = value
        self._semaphore.release()
        return self
    
    def reset(self):
        return self.progress(value=0.0)
    
    def start(self):
        self.stop()
        self._semaphore.acquire()
        self._activateTimers = True
        self.logger.debug('Starting app.')
        self._semaphore.release()
        self.update()
        return self
    
    def stop(self, clear: bool=False):
        self._semaphore.acquire()
        self._activateTimers = False
        self.logger.debug('Stopping app.')
        if type(self._timer) is Timer:
            self._timer.cancel()
        if clear:
            self._lcd.clear()
        self._semaphore.release()
        return self
    
    def update(self):
        self._semaphore.acquire()
        if not self._activateTimers:
            return self # might have been cancelled in the meantime
        self._lcd.text(line=self._ps.generateProgressText(
            show_dots=self.num_dots > 0, show_percent=self.show_percent), row=1)
        self._lcd.text(line=self._ps.generateProgressBar(), row=2)

        if self._activateTimers:
            self._timer = Timer(interval=0.5, function=self.update)
            self._timer.start()

        self._semaphore.release()

        return self
