from abc import ABC, abstractmethod
from typing import Any

class NewsImpl(ABC):

    @abstractmethod
    def processItems(self, items: list[dict[str, Any]]):
        """
        This method is given the news items of newsapi.org and is supposed
        to return a processed list of items to be used in the template.
        """
        pass

