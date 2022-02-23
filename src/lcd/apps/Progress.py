from src.lcd.apps.LcdApp import LcdApp
from src.lcd.TextLCD import TextLCD
from threading import Timer, Semaphore
from typing import Callable
from src.lcd.ProgressString import ProgressString



class Progress(LcdApp):
    def __init__(self, lcd: TextLCD, strFn: Callable[[], str], show_percent: bool=True, num_dots: int=2):
        self._lcd = lcd
        self.strFn = strFn
        self.show_percent = show_percent
        self.num_dots = num_dots
        # To synchronize updating both LCD's lines
        self._semaphore = Semaphore(1)
        self._ps = ProgressString(strFn=strFn, num_dots=num_dots)
        self._activateTimers = False
        self._timer: Timer = None

    def progress(self, value: float):
        if value < 0.0 or value > 1.0:
            raise Exception('progress must be in [0.0, 1.0].')
        self._ps.progress = value
        return self
    
    def start(self):
        self.stop()
        self._activateTimers = True
        self.update()
        return self
    
    def stop(self, clear: bool=False):
        self._activateTimers = False
        if type(self._timer) is Timer:
            self._timer.cancel()
        if clear:
            self._lcd.clear()
        return self
    
    def update(self):
        self._semaphore.acquire()
        self._lcd.text(line=self._ps.generateProgressText(
            show_dots=self.num_dots > 0, show_percent=self.show_percent), row=1)
        self._lcd.text(line=self._ps.generateProgressBar(), row=2)
        self._semaphore.release()

        if self._activateTimers:
            self._timer = Timer(interval=0.5, function=self.update)
            self._timer.start()

        return self
