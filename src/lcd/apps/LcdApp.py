from abc import ABC, abstractmethod


class LcdApp(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass
