from src.NewsImpl import NewsImpl
from typing import Any


class MyNewsImpl(NewsImpl):

    def processItems(self, items: list[dict[str, Any]]):
        """
        We use this method to sort some of the items.
        """

        items_ntv = []
        items_others = []

        for item in items:
            item = item.copy()
            item['title'] = item['title'][0:item['title'].rindex(' - ')]
            if 'n-tv' in item['source']['name'].lower():
                items_ntv.append(item)
            else:
                items_others.append(item)
        
        return items_ntv + items_others
