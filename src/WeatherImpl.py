from abc import ABC, abstractmethod

class WeatherImpl(ABC):

    @property
    @abstractmethod
    def currentTemp(self) -> float:
        """
        Abstract property that returns the current temperature as °C in the
        main location (if more than one configured).
        """
        pass
