from flask import Flask, render_template, send_from_directory
from flask.json import JSONEncoder
from datetime import datetime, timedelta


def _static_serve(path):
    return send_from_directory(directory='../web', path=path)

def _add_header(res):
    res.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    res.headers['Pragma'] = 'no-cache'
    res.headers['Expires'] = '0'
    return res


class MyJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            ic = obj.isocalendar()
            return {
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'iso_weekday': ic.weekday,
                'iso_week': ic.week,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'ts': obj.timestamp(),
                'utc_offset': None if obj.tzinfo is None else obj.tzinfo.utcoffset(obj).total_seconds()
            }
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        if hasattr(obj, 'dict'):
            return obj.dict()
        return super(MyJSONEncoder, self).default(o=obj)


_api = Flask(
    import_name=__name__,
    template_folder='../web/templates')
_api.json_encoder = MyJSONEncoder

# Disable caching
_api.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
_api.config['TEMPLATES_AUTO_RELOAD'] = True
_api.after_request(f=_add_header)



class Api:

    def __init__(self):
        self.routes = set()
        self.addRoute('/web/<path:path>', _static_serve)

    def run(self, host: str='127.0.0.1', port: int=4000):
        _api.run(host=host, port=port)
        return self

    def addRoute(self, route, fn):
        if route in self.routes:
            raise Exception(f'The route {route} already exists.')

        self.routes.add(route)
        _api.add_url_rule(rule=route, view_func=fn)

        return self

