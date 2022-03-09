from src.NewsImpl import NewsImpl
from typing import Any
from src.SelfResetLazy import SelfResetLazy
from functools import cmp_to_key
from jsons import loads
from os.path import abspath, join
import requests


class MyNewsImpl(NewsImpl):

    def __init__(self, conf: dict[str, Any], data_folder: str) -> None:
        super().__init__()
        self.conf = conf
        self.data_folder = data_folder

        def getHeadlineItems(urlKey: str):
            url: str = self.conf['urls'][urlKey]['url']
            url = url.replace('__APIKEY__', self.conf['api_key'])
            raw = requests.get(url=url).text
            data = loads(raw)['articles']

            with open(file=abspath(join(self.data_folder, f'news_{urlKey}.json')), mode='w', encoding='utf-8') as fp:
                fp.write(raw)

            return data
        
        self._lazies: dict[str, SelfResetLazy[str]] = {}

        for key in self.conf['urls'].keys():
            self._lazies[key] = SelfResetLazy(resource_name=f'headlines({key})', fnCreateVal=lambda key=key: getHeadlineItems(key), resetAfter=float(self.conf['urls'][key]['interval']))
    
    @property
    def items(self):
        items = []
        for lazy in self._lazies.values():
            items += lazy.value

        filter_terms = list(map(lambda s: s.lower(), self.conf['filter']))

        def s(n: str=None):
            if n is None:
                n = ''
            return n.lower()
        
        items_filtered = []

        for item in items:
            cont = True
            for term in map(lambda s: s.lower(), filter_terms):
                if term in s(item['title']) or term in s(item['description']) or term in s(item['author']) or term in s(item['source']['name']):
                    cont = False
                    break
            
            if not cont:
                continue

            if ' - ' in item['title']:
                item['title'] = item['title'][0:item['title'].rindex(' - ')]
            
            items_filtered.append(item)
        
        items_filtered.sort(
            reverse=True, key=cmp_to_key(lambda a, b: -1 if a['publishedAt'] < b['publishedAt'] else 1))
        
        return items_filtered
