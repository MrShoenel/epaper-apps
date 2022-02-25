import os
import logging
import calendar
import pathlib
import atexit
import locale
from typing import Dict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from json import dumps, load
from src.CustomFormatter import CustomFormatter
from src.CalendarMerger import CalendarMerger
from src.ButtonsAndLeds import ButtonsAndLeds, Button, Led
from src.Api import Api
from src.state.StateManager import StateManager
from src.state.DisplayStateMachines import ePaperStateMachine, TextLcdStateMachine
from flask import render_template

if os.name == 'posix':
    import RPi.GPIO as GPIO
    from src.ButtonsAndLeds import ButtonsAndLeds, Button, Led
    atexit.register(lambda: GPIO.cleanup())

    


class Configurator:
    """
    Main class for all of the e-Paper tools and applications. Reads
    a config.json and sets up everything accordingly.
    """

    GPIO_SET_UP = False

    def __init__(self, config):
        self.config = config
        if os.name == 'posix' and not Configurator.GPIO_SET_UP:
            GPIO.setmode(GPIO.BCM) # We do this once application-wide
            GPIO.setwarnings(True) # Should never be hidden, that'd be stupid
            Configurator.GPIO_SET_UP = True

        # For async firing of callbacks etc.
        self._tpe = ThreadPoolExecutor(max_workers=2)
        atexit.register(lambda: self._tpe.shutdown())

        data_folder = config['general']['data_folder'][os.name]
        pathlib.Path(data_folder).mkdir(parents=True, exist_ok=True)
        CustomFormatter.setLevel(level=getattr(logging, config['general']['log_level'], None))

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
        self.logger.debug(f'Read configuration: {dumps(config)}')
        
        # Set locale:
        locale.setlocale(locale.LC_ALL, config['general']['locale'])
        self.logger.debug(f'The current locale is {locale.getlocale()}')

        self.api: Api = Api()
        self.calendar: CalendarMerger = None
        self.epaperStateMachine: ePaperStateMachine = None
        self.hasTextLcd: bool = False
        self.textLcdStateMachine: TextLcdStateMachine = None
        self.ctrl: ButtonsAndLeds = None
    

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

            # We'll register our own callback for general actions, whenever there is
            # a transition.
            # self.epaperStateMachine.beforeInit += self.beforeInitCallback
            self.epaperStateMachine.beforeInit += lambda **kwargs: self._tpe.submit(self.beforeInitCallback, **kwargs)

            # The LCD is controlled solely by the e-paper, as it depends on
            # the actions applicable to it. So we'll set up the hooks here.
            self.epaperStateMachine.beforeInit += lambda **kwargs: self.textLcdStateMachine.activate(transition='show-progress')
            self.epaperStateMachine.afterFinalize += lambda **kwargs: self.textLcdStateMachine.activate(transition='show-datetime')
            def activationProgress(progress: float, **kwargs):
                self.textLcdStateMachine.getApp('show-progress').progress(progress)
            self.epaperStateMachine.activateProgress += activationProgress
        
        return self
    
    def beforeInitCallback(self, sm: StateManager, state_from: str, state_to: str, transition: str, **kwargs):
        """
        In this method we will check if there are actions associated with
        the transition in question. All actions will be triggered in series.
        """
        if transition is None:
            return # Happens during initialization of state machines
        conf = self.config['state_managers']['epaper']

        # First we need to find the transition that is currently triggered.
        trans = list(filter(lambda trans: trans['from'] == state_from and trans['to'] == state_to and trans['name'] == transition, conf['transitions']))
        if len(trans) != 1:
            raise Exception('Cannot identify the correct transition.')
        
        for action_name in trans[0]['actions']:
            actions = list(filter(lambda a: a['name'] == action_name, conf['actions']))
            if len(actions) == 1:
                action = actions[0]
                outputs = list(filter(lambda outp: outp['name'] == action['use_output'], self.config['outputs']))
                if len(outputs) == 0:
                    continue

                args = action['args']
                led = self.ctrl.getLed(name=action['use_output'])
                duration = self.epaperStateMachine.lastDuration(state_to=state_to)
                if type(args['duration']) is float:
                    duration = args['duration']
                if args['activity'] == 'burn':
                    self.logger.debug(f'Triggering action "burn" for {led.name} for a duration of {format(duration, ".2f")} seconds.')
                    self._tpe.submit(lambda: self.ctrl.burnLed(led=led, burn_for=duration))
                elif args['activity'] == 'blink':
                    self.logger.debug(f'Triggering action "blink" for {led.name} for a duration of {format(duration, ".2f")} seconds with a frequency of {args["freq"]} Hz.')
                    self._tpe.submit(lambda: self.ctrl.blinkLed(led=led, duration=duration, freq=args['freq']))

    def initStateMachines(self):
        self.logger.debug('Initializing state machines.')

        self.textLcdStateMachine.init()
        self.epaperStateMachine.init()

        self.logger.debug('Finished initializing state machines.')
        return self

    def setupBtnLedControl(self):
        self.logger.info('Setting up Button- and Led controls.')
        self.ctrl = ButtonsAndLeds()

        for c in self.config['inputs']:
            self.ctrl.addButton(pin=c['pin'], name=c['name'], bounce_time=c['bounce_time'])
        
        leds: Dict[str, Led] = {}
        for c in self.config['outputs']:
            leds[c['name']] = self.ctrl.addLed(pin=c['pin'], name=c['name'], burn_for=2)
        
        def button_callback(btn: Button):
            if self.epaperStateMachine.busy:
                self.logger.debug('The ePaperStateMachine is currently busy. Ignoring button press.')
                # Flash the red LED for some time
                self.ctrl.blinkLed(led=leds['led-red'], freq=10, duration=3)
                return self

            # find associated config:
            c = list(filter(lambda conf: btn.name==conf['name'], self.config['inputs']))[0]
            # Check if this button triggers one of the available transitions:
            at = set(map(lambda trans: trans['name'], self.epaperStateMachine.availableTransitions()))
            common = at.intersection(set(c['transitions']))
            if len(common) == 1:
                # We will not wait for it, nor are we interested in the result.
                # Activating an e-paper state takes a long time and is a synchronized method.
                self._tpe.submit(lambda: self.epaperStateMachine.activate(transition=list(at)[0]))
            
            # let's also check if this button press has an output action:
            if 'output' in c and c['output']['name'] in leds.keys():
                led = leds[c['output']['name']]
                # We will not wait for this to be finished, either
                self.ctrl.burnLed(led=led, burn_for=c['output']['duration'])

        # Note that these callbacks are fired in an extra thread already
        # by the ButtonAndLeds instance.
        self.ctrl.on_button += button_callback

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
                day_names=list(map(lambda str: str.capitalize(), calendar.day_name)),
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
