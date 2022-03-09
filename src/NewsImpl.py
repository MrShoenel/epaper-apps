from abc import ABC, abstractmethod
from typing import Any

class NewsImpl(ABC):

    @property
    @abstractmethod
    def items(self):
        """
        Abstract method that shall return a list of news items, with all
        properties as required by the template, and in the desired order.
        """
        pass
