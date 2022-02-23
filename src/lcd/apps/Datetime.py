import calendar
from datetime import datetime
from src.lcd.TextLCD import TextLCD
from src.lcd.apps.LcdApp import LcdApp
from src.lcd.ScrollString import BounceString, ScrollString
from typing import Callable
from threading import Timer
from src.CustomFormatter import CustomFormatter


def pad(s: str):
    s = '' + str(s)
    if len(s) < 2:
        return '0' + s
    return s


class Datetime(LcdApp):

    def __init__(self, lcd: TextLCD, mode: str='bounce', l1interval: float=0.999, l2interval: float=4.75):
        self._lcd = lcd
        self._l1interval = l1interval
        self._l2interval = l2interval

        self.scroll = mode == 'bounce'

        def timeFn():
            dt = datetime.now()
            line = f'{pad(dt.hour)}:{pad(dt.minute)}:{pad(dt.second)}'
            return line
        
        def dateFn():
            dt = datetime.now()
            line = f'{pad(dt.day)}.{calendar.month_abbr[dt.month]}+{pad(dt.year)}'
            return line


        self._s1 = BounceString(strFn=timeFn) if self.scroll else ScrollString(strFn=timeFn)
        self._s1Fn = self._s1.bounce if self.scroll else self._s1.scroll
        self._s2 = BounceString(strFn=dateFn) if self.scroll else ScrollString(strFn=dateFn)
        self._s2Fn = self._s2.bounce if self.scroll else self._s2.scroll

        self._activateTimers = False
        self._timerl1: Timer = None
        self._timerl2: Timer = None

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def start(self):
        self.stop()
        self._activateTimers = True
        self.logger.debug('Starting app.')

        self.writeTime()
        self.writeDate()

        return self
    
    def stop(self, clear: bool=True):
        self._activateTimers = False
        self.logger.debug('Stopping app.')
        if type(self._timerl1) is Timer:
            self._timerl1.cancel()
        if type(self._timerl2) is Timer:
            self._timerl2.cancel()
        
        if clear:
            self._lcd.clear()

        self._s1.reset()
        self._s2.reset()
        
        return self
    
    def writeTime(self):
        self._lcd.text(line=self._s1Fn(), row=1)
        if self._activateTimers:
            self._timerl1 = Timer(interval=self._l1interval, function=self.writeTime)
            self._timerl1.start()


    def writeDate(self):
        self._lcd.text(line=self._s2Fn(), row=2)
        if self._activateTimers:
            self._timerl2 = Timer(interval=self._l2interval, function=self.writeDate)
            self._timerl2.start()

        
