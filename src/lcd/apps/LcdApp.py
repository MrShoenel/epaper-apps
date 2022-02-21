from abc import ABC, abstractmethod


class LcdApp(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass
