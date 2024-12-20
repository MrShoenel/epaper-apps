from datetime import datetime, timedelta
from src.WeatherImpl import WeatherImpl
from src.CustomFormatter import CustomFormatter
from src.SelfResetLazy import SelfResetLazy
from os.path import abspath, join, exists
from typing import Any
from jsons import loads
from src.weather.MyWeatherImpl import FORECAST_TYPE
import requests

class OpenMeteoWeatherImpl(WeatherImpl):
    def __init__(self, conf: dict[str, Any], data_folder: str) -> None:
        super().__init__()
        
        self.conf = conf
        self.data_folder = data_folder
        
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self._lazies: dict[str, SelfResetLazy[dict[Any, Any]]] = {}

        for key in self.conf['locations'].keys():
            self._lazies[key] = SelfResetLazy(resource_name=f'weather({key})', fnCreateVal=lambda key=key: self.getWeather(key), resetAfter=float(self.conf['locations'][key]['interval']))
            self._lazies[key].valueFuture
        
        self.primary_loc: str = list(self.conf['locations'].keys())[0]
        self.logger.debug(f'The primary location for weather is "{self.primary_loc}"')

        self.last_temp: float = float('nan')
        self.last_hourly: list[str] = []
    

    def getWeather(self, key: str) -> dict:
        c = self.conf['locations'][key]
        url: str = c['url'] \
            .replace('__LAT__', str(c['lat'])) \
            .replace('__LON__', str(c['lon'])) \
            .replace('__TZ__', c['timezone'])

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
        """Do not block in this method."""
        lazy = self._lazies[self.primary_loc]

        def set_current_temp(res: dict) -> float:
            # The response has an array of hourly forecasts and we got to find the index first.
            # If the current minute is > 30, we take the forecast from the next hour.
            dt = datetime.now()
            if dt.minute > 30:
                dt += timedelta(hours=1.0)
            
            try:
                idx: int = res['hourly']['time'].index(dt.strftime('%Y-%m-%dT%H:00'))
                self.last_temp = res['hourly']['temperature_2m'][idx]
            except:
                self.last_temp = float('nan')
            return self.last_temp
        
        if lazy.hasValueVolatile:
            set_current_temp(lazy.value)
        else:
            lazy.valueFuture.add_done_callback(lambda future: set_current_temp(future.result()))
        
        return self.last_temp


    @property
    def hourly(self) -> list[str]:
        """Do not block in this method."""
        lazy = self._lazies[self.primary_loc]
        
        def set_hourly(res: dict) -> None:
            self.last_hourly = res['hourly']['time']
        
        if lazy.hasValueVolatile:
            set_hourly(lazy.value)
        else:
            lazy.valueFuture.add_done_callback(lambda future: set_hourly(future.result()))
        
        return self.last_hourly
        
    
    @property
    def daily(self) -> list[dict[str, Any]]:
        """
        Abstract property that returns the weather for the next few days,
        also by day.
        """
        raise NotImplementedError()
    
    def lat_lon(self, location: str=None) -> tuple[float, float]:
        return (0.0, 0.0)
    
    def forecast_location(self, location: str=None, type: FORECAST_TYPE=FORECAST_TYPE.DAILY) -> list[dict[str, Any]]:
        return []
    