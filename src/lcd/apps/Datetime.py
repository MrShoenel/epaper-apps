import calendar
from datetime import datetime
from time import sleep
from src.lcd.TextLCD import TextLCD
from src.lcd.apps.LcdApp import LcdApp
from src.lcd.ScrollString import BounceString, ScrollString
from threading import Thread, Semaphore
from src.CustomFormatter import CustomFormatter
from src.SelfResetLazy import SelfResetLazy
from src.WeatherImpl import WeatherImpl
from typing import Callable


def pad(s: str):
    s = '' + str(s)
    if len(s) < 2:
        return '0' + s
    return s


def sleep_partitioned(fn_do_sleep: Callable[[], bool], secs, by=1.0):
    while secs > 0.0 and fn_do_sleep():
        fraction = min(secs, by)
        sleep(fraction)
        secs -= fraction


class Datetime(LcdApp):
    def __init__(self, lcd: TextLCD, mode: str='bounce', l1interval: float=0.999, l2interval: float=4.75, l1every: int=2, l2every: int=1, showTemp: bool=True):
        self._lcd = lcd
        self._l1interval = l1interval
        self._l2interval = l2interval
        self._l1every = l1every
        self._l2every = l2every
        self._showTemp = showTemp
        self._semaphore = Semaphore(1)

        def getWeatherService() -> WeatherImpl:
            # We have to use this hack to avoid circular imports.
            from src.Configurator import Configurator
            return Configurator.instance().getService(WeatherImpl)

        self.lazy_weather: SelfResetLazy[WeatherImpl] = SelfResetLazy(resource_name='weather', fnCreateVal=getWeatherService)

        self.scroll = mode == 'bounce'

        def timeFn():
            dt = datetime.now()
            line = f'{dt.hour}:{pad(dt.minute)}:{pad(dt.second)}'

            if self._showTemp:
                temp = self.lazy_weather.value.currentTemp
                line += f' {format(round(temp, 1), ".1f")}{chr(223)}C'
            return line
        
        def dateFn():
            dt = datetime.now()
            line = f'{dt.day}. {calendar.month_abbr[dt.month].capitalize()} {pad(dt.year)}'
            return line

        self._s1 = BounceString(strFn=timeFn) if self.scroll else ScrollString(strFn=timeFn)
        self._s1Fn = self._s1.bounce if self.scroll else self._s1.scroll
        self._s2 = BounceString(strFn=dateFn) if self.scroll else ScrollString(strFn=dateFn)
        self._s2Fn = self._s2.bounce if self.scroll else self._s2.scroll
        self._t1: Thread = None
        self._t2: Thread = None

        self._activate = False

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def reset(self):
        return self # nothing to do here
    
    def start(self):
        self.stop(clear=True)

        self._semaphore.acquire()
        self._activate = True

        def fnTime():
            cnt = 0
            while self._activate:
                by = 0
                if cnt == self._l1every:
                    by = 1
                    cnt = 0

                self._lcd.text(line=self._s1Fn(by=by), row=1)
                # Continue sleeping for as long as this is active
                sleep_partitioned(fn_do_sleep=lambda: self._activate, secs=self._l1interval, by=0.5)
                cnt += 1

        self._t1 = Thread(target=fnTime)
        self._t1.start()


        def fnDate():
            cnt = 0
            while self._activate:
                by = 0
                if cnt == self._l2every:
                    by = 1
                    cnt = 0

                self._lcd.text(line=self._s2Fn(by=by), row=2)
                sleep_partitioned(fn_do_sleep=lambda: self._activate, secs=self._l2interval, by=0.5)
                cnt += 1
        
        self._t2 = Thread(target=fnDate)
        self._t2.start()

        self._semaphore.release()
        return self
    

    def stop(self, clear: bool=True):
        self._semaphore.acquire()
        self._activate = False
        if type(self._t1) is Thread and self._t1.is_alive():
            self._t1.join()
        if type(self._t2) is Thread and self._t2.is_alive():
            self._t2.join()
        
        if clear:
            self._lcd.clear()
        
        self._semaphore.release()
        return self
