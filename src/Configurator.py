import logging
import threading
import calendar
from datetime import datetime, timedelta
from json import dumps, load
from src.CustomFormatter import CustomFormatter
from src.CalendarMerger import CalendarMerger
from src.Api import Api
from flask import render_template, request




class Configurator:
    """
    Main class for all of the e-Paper tools and applications. Reads
    a config.json and sets up everything accordingly.
    """

    def __init__(self, config):
        self.config = config
        CustomFormatter.setLevel(level=getattr(logging, config['general']['log_level'], None))

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
        self.logger.debug(f'Read configuration: {dumps(config)}')

        self.api: Api = Api()
        self.calendar: CalendarMerger = None
    

    def fromJson(path: str='config.json'):
        with open(file=path, mode='r', encoding='utf-8') as fp:
            return Configurator(config=load(fp=fp))
    
    def startApi(self, blocking: bool=False):
        c = self.config['api']
        self.api.run(host=c['host'], port=c['port'], blocking=blocking)
        return self
    
    def stopApi(self):
        self.api.stop()
        return self
    
    def setupCalendar(self):
        self.calendar = CalendarMerger(cal_config=self.config['calendar'])
        
        self.logger.info(f'Finished setting up {self.calendar.__class__.__name__}.')

        # Add calendar-related routes:
        self.api.addRoute(route='/calendar/ical', fn=self.calendar.apiCal)
        
        self.api.addRoute(route='/calendar/3-way-1-day', fn=lambda: render_template(
            'calendar/3-way-1-day.html',
            time_now=datetime.now().astimezone(),
            events_of_the_day=self.calendar.eventsToday() + self.calendar.todosToday(),
            weekday_events=self.calendar.weekdayItems(num_weeks=6, start_dt=datetime.today().astimezone() - timedelta(weeks=1)),
            day_names=list(calendar.day_name),
            view_config=self.config['views']['3-way-1-day']
        ))

        self.logger.debug('Added calendar-related routes.')

        return self

    def getScreenConfig(self, name: str):
        if not name in self.config['screens']:
            raise Exception(f'There is no configured screen with the name "{name}".')
        conf = self.config['screens'][name]

        api = self.config['api']
        host = api['host']
        port = api['port']
        conf['url'] = f'http://{host}:{port}/calendar/{name}'
        return conf

