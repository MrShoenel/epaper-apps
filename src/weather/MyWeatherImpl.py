from datetime import datetime
from enum import Enum
from src.Api import MyJSONEncoder
from src.WeatherImpl import WeatherImpl
from src.CustomFormatter import CustomFormatter
from src.SelfResetLazy import SelfResetLazy
from os.path import abspath, join, exists
from typing import Any
from jsons import loads
from pandas import json_normalize
from collections.abc import Sequence
import requests




class FORECAST_TYPE(Enum):
    HOURLY = 'hourly'
    DAILY = 'daily'


class MyWeatherImpl(WeatherImpl):

    def __init__(self, conf: dict[str, Any], data_folder: str) -> None:
        super().__init__()
        self.conf = conf
        self.data_folder = data_folder
        
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self._lazies: dict[str, SelfResetLazy[dict[Any, Any]]] = {}

        for key in self.conf['locations'].keys():
            self._lazies[key] = SelfResetLazy(resource_name=f'weather({key})', fnCreateVal=lambda key=key: self.getWeather(key), resetAfter=float(self.conf['locations'][key]['interval']))
            self._lazies[key].valueFuture # Trigger creation of value, but don't wait for the Future
            # Otherwise, we'll get a lot of messages
            # self._lazies[key].logger.level = logging.WARN
        
        self.primary_loc = list(self.conf['locations'].keys())[0]
        self.logger.debug(f'The primary location for weather is "{self.primary_loc}"')

        self.last_temp: float = 0.0
    
    def getWeather(self, key: str) -> dict:
        c = self.conf['locations'][key]
        url: str = c['url'].replace('__APIKEY__', self.conf['api_key']) \
            .replace('__LAT__', str(c['lat'])) \
            .replace('__LON__', str(c['lon'])) \
            .replace('__UNITS__', c['units'])

        file = abspath(join(self.data_folder, f'weather_{key}.json'))

        try:
            res = requests.get(url=url, timeout=10)
            if res.status_code != 200:
                raise Exception(f'Cannot obtain weather, got status code {res.status_code}, result was: "{res.text}"')
            raw = res.text
            with open(file=file, mode='w', encoding='utf-8') as fp:
                fp.write(raw)
            return loads(raw)
        except Exception as e:
            if exists(file):
                self.logger.warn(f'Cannot load weather, got error: "{str(e)}", returning potentially old weather for "{key}".')
                with open(file=file, mode='r', encoding='utf-8') as fp:
                    return loads(fp.read())
            else:
                self.logger.error(f'Cannot load weather for "{key}" and no previous state exists.')
                raise e


    @property
    def currentTemp(self) -> float:
        """
        Implemented in a way such that it never blocks.
        """
        lazy = self._lazies[self.primary_loc]

        def setTemp(temp: float):
            self.last_temp = temp

        lazy.valueFuture.add_done_callback(lambda fut: setTemp(float(fut.result()['current']['temp'])))

        # These properties do not block
        temp = lazy.valueVolatile
        if type(temp) is dict and lazy.hasValueVolatile:
            self.last_temp = float(temp['current']['temp'])

        return self.last_temp
    
    def lat_lon(self, location: str=None) -> tuple[float, float]:
        if location is None:
            location = self.primary_loc
        v = self._lazies[location].value
        return (v['lat'], v['lon'])
    
    def forecast_location(self, location: str=None, type: FORECAST_TYPE=FORECAST_TYPE.DAILY) -> list[dict[str, Any]]:
        if location is None:
            location = self.primary_loc
        lazy = self._lazies[location]

        def unpack_array(item):
            if isinstance(item['weather'], Sequence):
                item['weather'] = item['weather'][0]
            return item
        
        mje = MyJSONEncoder()
        def convert_timestamps(item):
            check_keys = ['dt', 'sunrise', 'sunset', 'moonrise', 'moonset']
            for key in check_keys:
                if key in item and isinstance(item[key], int) and item[key] > 99999:
                    item[key] = mje.default(datetime.fromtimestamp(item[key]))
            return item

        
        try:
            # unpack nested array (if any),
            fc = list(map(lambda item: unpack_array(convert_timestamps(item.copy())), lazy.value[type.value]))
            # then flatten nested properties
            temp = json_normalize(fc)
            return temp.to_dict('records')
        except Exception as e:
            self.logger.error(f'Cannot get hourly weather, exception was: "{str(e)}"')
            return []
            


    @property
    def hourly(self) -> list[dict[str, Any]]:
        return self.forecast_location(location=self.primary_loc, type=FORECAST_TYPE.HOURLY)
    
    @property
    def daily(self) -> list[dict[str, Any]]:
        return self.forecast_location(location=self.primary_loc, type=FORECAST_TYPE.DAILY)
