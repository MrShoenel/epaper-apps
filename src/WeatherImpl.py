from abc import ABC, abstractmethod
from typing import Any

class WeatherImpl(ABC):

    @property
    @abstractmethod
    def currentTemp(self) -> float:
        """
        Abstract property that returns the current temperature as °C in the
        main location (if more than one configured).
        """
        pass

    @property
    @abstractmethod
    def hourly(self) -> list[dict[str, Any]]:
        """
        Abstract property that returns the weather for the next few hours,
        also by hour.
        """
        pass
