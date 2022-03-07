from src.NewsImpl import NewsImpl
from typing import Any
from functools import cmp_to_key


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

        items_ntv.sort(
            reverse=True, key=cmp_to_key(lambda a, b: -1 if a['publishedAt'] < b['publishedAt'] else 1))
        items_others.sort(
            reverse=True, key=cmp_to_key(lambda a, b: -1 if a['publishedAt'] < b['publishedAt'] else 1))

        return items_ntv + items_others
