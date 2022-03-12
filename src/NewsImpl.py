from abc import ABC, abstractmethod

class NewsImpl(ABC):

    @property
    @abstractmethod
    def items(self) -> list:
        """
        Abstract property that shall return a list of news items, with all
        properties as required by the template, and in the desired order.
        """
        pass
