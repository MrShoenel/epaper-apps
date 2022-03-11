from src.NewsImpl import NewsImpl
from typing import Any
from src.SelfResetLazy import SelfResetLazy
from functools import cmp_to_key
from jsons import loads
from os.path import abspath, join, exists
from src.CustomFormatter import CustomFormatter
import requests
from html import unescape


class MyNewsImpl(NewsImpl):

    def __init__(self, conf: dict[str, Any], data_folder: str) -> None:
        super().__init__()
        self.conf = conf
        self.data_folder = data_folder
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self._lazies: dict[str, SelfResetLazy[list[Any]]] = {}

        for key in self.conf['urls'].keys():
            self._lazies[key] = SelfResetLazy(resource_name=f'headlines({key})', fnCreateVal=lambda key=key: self.getHeadlineItems(key), resetAfter=float(self.conf['urls'][key]['interval']))
    
    def getHeadlineItems(self, urlKey: str):
        url: str = self.conf['urls'][urlKey]['url']
        url = url.replace('__APIKEY__', self.conf['api_key'])
        raw = requests.get(url=url).text
        data = loads(raw)
        file = abspath(join(self.data_folder, f'news_{urlKey}.json'))

        if data['status'] != 'ok':
            # Most likely rate-limited, but doesn't matter.
            if exists(file):
                self.logger.warn(f'Got error: "{data["status"]["code"]}", "{data["status"]["message"]}", returning potentially old news for "{urlKey}".')
                with open(file=file, mode='r', encoding='utf-8') as fp:
                    return loads(fp.read())
            else:
                self.logger.error(f'Cannot load news and no previous items exist. Error was: "{data["status"]["code"]}", "{data["status"]["message"]}".')
                return []

        with open(file=file, mode='w', encoding='utf-8') as fp:
            fp.write(raw)

        return data['articles']
    
    @property
    def items(self):
        def s(n: str=None):
            if n is None:
                n = ''
            return n.lower()

        items_filtered = []

        for key, lazy in self._lazies.items():
            conf = self.conf['urls'][key]

            for item in lazy.value:
                if item['title'] is None or item['description'] is None:
                    continue

                item = item.copy() # Do not modify the original!
                if ' - ' in item['title']:
                    item['title'] = item['title'][0:item['title'].rindex(' - ')]
                
                item['title'] = unescape(item['title'])
                item['description'] = unescape(item['description'])

                cont = False
                for term in map(lambda s: s.lower(), conf['filter']):
                    if term in s(item['title']) or term in s(item['description']) or term in s(item['author']) or term in s(item['source']['name']):
                        cont = True
                        break

                if cont:
                    continue

                items_filtered.append(item)

        items_filtered.sort(
            reverse=True, key=cmp_to_key(lambda a, b: -1 if a['publishedAt'] < b['publishedAt'] else 1))
        
        return items_filtered
