from src.NewsImpl import NewsImpl
from typing import Any
from functools import cmp_to_key


class MyNewsImpl(NewsImpl):

    def __init__(self, conf: dict[str, Any]) -> None:
        super().__init__()
        self.conf = conf

    def processItems(self, items: list[dict[str, Any]]):
        """
        We use this method to sort some of the items.
        """

        items_ntv = []
        items_others = []

        filter_terms = list(map(lambda s: s.lower(), self.conf['filter']))

        def s(n: str=None):
            if n is None:
                return ''
            return n

        for item in items:
            cont = True
            for term in map(lambda s: s.lower(), filter_terms):
                if term in s(item['title']).lower() or term in s(item['description']).lower() or term in s(item['author']).lower():
                    cont = False
                    break
            
            if not cont:
                continue

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
