from src.lcd.apps.LcdApp import LcdApp
from src.lcd.TextLCD import TextLCD
from src.lcd.ScrollString import ScrollString, BounceString
from threading import Timer
from typing import Callable
from math import ceil



class Progress(LcdApp):
    def __init__(self, lcd: TextLCD, strFn: Callable[[], str], show_percent: bool=True, show_dots: bool=True):
        self._lcd = lcd
        self.progress = 0
        self.strFn = strFn
        self.show_percent = show_percent
        self.show_dots = show_dots
        self._num_dots = 0
        self._timer: Timer = None

    async def start(self):
        self._timer = Timer(interval=0.5, function=self.update)
        self._timer.start()
        return self

    async def stop(self):
        if type(self._timer) is Timer:
            self._timer.cancel()
            del self._timer
        
        self._lcd.clear()
        
        return self

    def update(self):
        # Here we gonna write up-2-date strings to the LCD. The first
        # row will be string followed by dots, followed by a percentage
        # (right-aligned)

        line1 = self.strFn()[0:self._lcd.cols]
        if self.show_dots:
            preserve = 3 + (4 if self.show_percent else 0)
            self._num_dots %= 3 # goes to 0,1,2
            dots = self._num_dots + 1
            line1 = line1[0:(self._lcd.cols - preserve)] + dots
        if self.show_percent:
            percent = '{:3.0f}%'.format(int(self.progress * 100))
            line1 += percent
        
        line2 = self.generateProgressBar()
        
        self._lcd.text(line=line1, row=1)
        self._lcd.text(line=line2, row=2)

        self.start() # Re-run timer
        return self

    def generateProgressBar(self):
        cols = self._lcd.cols
        pCols = cols - 2
        numUsed = int(ceil(self.progress * 100.0) / pCols)
        arrow = '>' if numUsed < pCols else ''

        return f'[{numUsed * '#'}{arrow}]'
