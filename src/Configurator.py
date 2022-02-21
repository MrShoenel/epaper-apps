import os
import logging
import threading
import calendar
import pathlib
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
        data_folder = config['general']['data_folder'][os.name]
        pathlib.Path(data_folder).mkdir(parents=True, exist_ok=True)
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

        def render3way1day():
            c = self.config['views']['3-way-1-day']['calendar']
            num_weeks = c['num_weeks']
            start_split = c['start_dt'][0].split('-')
            start_dt = datetime.today().astimezone() # Start today; we'll support 'today' and 'monthstart'
            if start_split[0] == 'monthstart' and start_dt.day > 1:
                # Rewind to first day of month
                start_dt = start_dt - timedelta(days=start_dt.day-1)
                if start_dt.isoweekday() > 1:
                    # Rewind to first weekday, perhaps into last day of previous month
                    start_dt = start_dt - timedelta(days=start_dt.isoweekday() - 1)
            
            if len(start_split) > 1:
                # We'll have to subtract some time; supported format is 'n_weeks', so we'll look for 'n'
                start_dt = start_dt - timedelta(weeks=int(start_split[1].split('_')[0]))

            return render_template(
                'calendar/3-way-1-day.html',
                time_now=datetime.now().astimezone(),
                events_of_the_day=self.calendar.eventsToday() + self.calendar.todosToday(),
                weekday_events=self.calendar.weekdayItems(num_weeks=num_weeks, start_dt=start_dt),
                day_names=list(calendar.day_name),
                view_config=self.config['views']['3-way-1-day'])
        
        self.api.addRoute(route='/calendar/3-way-1-day', fn=render3way1day)

        def renderMultiWeek():
            c = self.config['views']['multi-week']
            num_weeks = c['num_weeks']
            start_split = c['start_dt'][0].split('-')
            start_dt = datetime.today().astimezone() # Start today; we'll support 'today' and 'monthstart'
            if start_split[0] == 'monthstart' and start_dt.day > 1:
                # Rewind to first day of month
                start_dt = start_dt - timedelta(days=start_dt.day-1)
                if start_dt.isoweekday() > 1:
                    # Rewind to first weekday, perhaps into last day of previous month
                    start_dt = start_dt - timedelta(days=start_dt.isoweekday() - 1)
            
            if len(start_split) > 1:
                # We'll have to subtract some time; supported format is 'n_weeks', so we'll look for 'n'
                start_dt = start_dt - timedelta(weeks=int(start_split[1].split('_')[0]))
            
            return render_template(
                'calendar/multi-week.html',
                time_now=datetime.now().astimezone(),
                weekday_events=self.calendar.weekdayItems(num_weeks=num_weeks, start_dt=start_dt),
                day_names=list(calendar.day_name),
                view_config=self.config['views']['multi-week'])
        
        self.api.addRoute(route='/calendar/multi-week', fn=renderMultiWeek)

        self.logger.debug('Added calendar-related routes.')

        return self
    
    def getGeneralConfig(self):
        return self.config['general']

    def getScreenConfig(self, name: str):
        if not name in self.config['screens']:
            raise Exception(f'There is no configured screen with the name "{name}".')
        conf = self.config['screens'][name]

        api = self.config['api']
        host = api['host']
        port = api['port']
        conf['url'] = f'http://{host}:{port}/calendar/{name}'
        return conf
