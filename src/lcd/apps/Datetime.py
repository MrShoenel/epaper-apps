from datetime import datetime
from src.lcd.TextLCD import TextLCD
from src.lcd.apps.LcdApp import LcdApp
from src.lcd.ScrollString import BounceString, ScrollString
from typing import Callable
from threading import Timer


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

        def timeFn():
            dt = datetime.now()
            return f'{pad(dt.hour)}:{pad(dt.minute)}:{pad(dt.second)}'
        
        def dateFn():
            dt = datetime.now()
            return f'{pad(dt.day)}.{calendar.month_abbr[dt.month]}+{pad(dt.year)}'


        self._s1 = BounceString(strFn=timeFn) if mode == 'bounce' else ScrollString(strFn=timeFn)
        self._s1Fn = self._s1.bounce if mode == 'bounce' else self._s1.scroll
        self._s2 = BounceString(strFn=dateFn) if mode == 'bounce' else ScrollString(strFn=dateFn)
        self._s2Fn = self._s2.bounce if mode == 'bounce' else self._s2.scroll

        self._activateTimers = False
        self._timerl1: Timer = None
        self._timerl2: Timer = None
    
    async def start(self):
        self._stop()
        self._activateTimers = True

        self._s1.reset()
        self._s2.reset()
        
        self._timerl1 = Timer(interval=self._l1interval, function=self.writeTime)
        self._timerl2 = Timer(interval=self._l2interval, function=self.writeDate)
        self._timerl1.start()
        self._timerl2.start()

        return self
    
    async def stop(self):
        self._activateTimers = False
        if type(self._timerl1) is Timer:
            self._timerl1.cancel()
            del self._timerl1
        if (type self._timerl2) is Timer:
            self._timerl2.cancel()
            del self._timerl2
        
        self._lcd.clear()
        
        return self
    
    def writeTime(self):
        self._lcd.text(line=self._s1Fn(), row=1)

    def writeDate(self):
        self._lcd.text(line=self._s2Fn(), row=2)

        
