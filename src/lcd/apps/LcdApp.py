from abc import ABC, abstractmethod


class LcdApp(ABC):
    @abstractmethod
    def start(self, **kwargs):
        pass

    @abstractmethod
    def stop(self, **kwargs):
        pass
