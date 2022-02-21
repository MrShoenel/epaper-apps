import os
import logging
import threading
import calendar
import pathlib
import asyncio
from datetime import datetime, timedelta
from json import dumps, load
from src.CustomFormatter import CustomFormatter
from src.CalendarMerger import CalendarMerger
from src.Api import Api
from src.ButtonsAndLeds import ButtonsAndLeds, Button, Led
from src.state.StateManager import StateManager
from src.state.DisplayStateMachines import ePaperStateMachine, TextLcdStateMachine
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
        self.epaperStateMachine: ePaperStateMachine = None
        self.hasTextLcd: bool = False
        self.textLcdStateMachine: TextLcdStateMachine = None
    

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
    
    def setupStateMachines(self):
        self.logger.info('Setting up state machines.')
        # Note that it requires the entire config.
        self.epaperStateMachine = ePaperStateMachine(config=self.config)

        if 'textlcd' in self.config['state_managers'].keys():
            self.hasTextLcd = True
            self.textLcdStateMachine = TextLcdStateMachine(config=self.config)

            # The LCD is controlled solely by the e-paper, as it depends on
            # the actions applicable to it. So we'll set up the hooks here.
            self.epaperStateMachine.beforeInit += lambda sm: self.textLcdStateMachine.activate(transition='show-progress')
            self.epaperStateMachine.afterFinalize += lambda sm: self.textLcdStateMachine.activate(transition='show-datetime')
            def activationProgress(sm: StateManager, progress: float):
                self.textLcdStateMachine.getApp('show-progress').progress = progress
            self.epaperStateMachine.activateProgress += activationProgress

    def initStateMachines(self):
        self.logger.debug('Initializing state machines.')

        async def temp():
            return asyncio.gather(*[
                self.epaperStateMachine.init(),
                self.textLcdStateMachine.init()
            ])

        asyncio.run(temp())
        self.logger.debug('Finished initializing state machines.')
        return self

    def setupBtnLedControl(self):
        self.logger.info('Setting up Button- and Led controls.')
        ctrl = ButtonsAndLeds()

        for c in self.config['inputs']:
            ctrl.addButton(pin=c['pin'], name=c['name'], bounce_time=c['bounce_time'])
        
        leds: Dict[str, Led] = {}
        for c in self.config['outputs']:
            leds[c['name']] = ctrl.addLed(pin=c['pin'], name=c['name'], burn_for=2)
        
        def button_callback(btn: Button):
            futures = []
            # find associated config:
            c = list(filter(lambda conf: btn.name==conf['name'], self.config['inputs']))[0]
            # Check if this button triggers one of the available transitions:
            at = set(map(lambda trans: trans.name, self.epaperStateMachine.availableTransitions()))
            common = at.intersection(set(c['transitions']))
            if len(common) == 1:
                futures.append(self.epaperStateMachine.activate(transition=list(at)[0]))
            
            # let's also check if this button press has an output action:
            if 'output' in c and c['output']['name'] in leds.keys():
                led = leds[c['output']['name']]
                futures.append(ctrl.burnLed(led=led, burn_for=c['output']['duration']))
            
            async def temp():
                return await asyncio.gather(*futures)
            
            asyncio.run(temp())

        ctrl.on_button += button_callback
    
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
