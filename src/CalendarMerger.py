import datetime
import pytz
import requests
import jsons
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from dateutil import tz
from typing import Any, Callable
from threading import Timer, Semaphore
from src.CustomFormatter import CustomFormatter
from datetime import datetime, timedelta
from icalendar import Calendar, Event, Todo
from recurring_ical_events import of



retry_strategy = Retry(
    total=10,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)


def ifelse(cond, fnTrue: Callable[[], Any], iffalse):
    if cond:
        return fnTrue()
    return iffalse


class DataEvent:

    def __init__(self, cal_name: str, created: datetime, start: datetime, end: datetime, title: str, desc: str, location: str, is_recurring: bool, is_task: bool=None, is_complete: bool=None, percent_complete: float=None):
        self.cal_name = cal_name
        self.created = DataEvent._utc2local(dt=created)
        self.start = DataEvent._utc2local(dt=start)
        self.end = DataEvent._utc2local(dt=end)
        self.duration = ifelse(type(start) == datetime and type(end) == datetime, lambda: end - start, None)
        self.title = title
        self.desc = desc
        self.location = location
        self.is_recurring = is_recurring
        self.is_task = is_task

        self.is_complete = is_complete
        if type(is_complete) is bool and is_complete == True:
            self.percent_complete = float(100)
        elif type(percent_complete) is float:
            self.percent_complete = percent_complete
            if int(percent_complete) == 100:
                self.is_complete = True

        if is_task is None:
            self.is_task = title.lower().startswith('[task]')
            if self.is_task:
                self.title = self.title[6:len(self.title)].strip()
                self.is_complete = '[done]' in title.lower()
    
    @staticmethod
    def _utc2local(dt: datetime):
        if type(dt) is not datetime:
            return dt

        utc = pytz.timezone('UTC')
        localtz = tz.tzlocal()

        if dt.tzinfo == utc:
            dt = dt.astimezone(tz=localtz)
        return dt

    
    def dict(self):
        return dict((key, value) for key, value in self.__dict__.items() if not callable(value) and not key.startswith('__'))
    
    def __json__(self):
        return jsons.dumps(obj=self.dict())
    
    def __str__(self):
        return self.__json__()


    @staticmethod
    def fromVevent(e, is_recurring: bool=None):
        return DataEvent(
            cal_name=ifelse('X-CALENDARNAME' in e.keys(), lambda: e["X-CALENDARNAME"], None),
            created=e["CREATED"].dt,
            start=e["DTSTART"].dt,
            end=e["DTEND"].dt,
            title=ifelse('SUMMARY' in e, lambda: e["SUMMARY"].strip(), None),
            desc=ifelse('DESCRIPTION' in e, lambda: e["DESCRIPTION"].strip(), None),
            location=ifelse('LOCATION' in e and not ''.__eq__(len(e["LOCATION"].strip())), lambda: e["LOCATION"].strip(), None),
            is_recurring=ifelse(is_recurring is None, lambda: True if 'X-ISRECURRENT' in e.keys() else False, is_recurring))
    
    @staticmethod
    def fromVtodo(t):
        return DataEvent(
            cal_name=ifelse('X-CALENDARNAME' in t.keys(), lambda: t["X-CALENDARNAME"], None),
            created=t["CREATED"].dt,
            start=ifelse('DTSTART' in t.keys(), lambda: t["DTSTART"].dt, None),
            end=ifelse('DUE' in t.keys(), lambda: t["DUE"].dt, None),
            title=t["SUMMARY"].strip(),
            desc=None,
            location=None,
            is_recurring=False,
            is_task=True,
            is_complete='STATUS' in t.keys() and t["STATUS"] == 'COMPLETED',
            percent_complete=ifelse('PERCENT-COMPLETE' in t.keys(), lambda: float(t["PERCENT-COMPLETE"]), None))



class IntervalCalendar:

    def __init__(self, name: str, url: str, interval: int, tz_indef: datetime.tzinfo=None):
        self.name = name
        self.url = url
        self.interval = interval
        self.tz_indef = tz_indef
        self.cal_text: str = None
        self.semaphore = Semaphore(value=1)

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self._timer: Timer = None
        if self.interval > 0:
            self._startTimer()
    
    def _stopTimer(self):
        if type(self._timer) is Timer and self._timer.is_alive():
            self._timer.cancel()
            self._timer = None
        return self

    def _startTimer(self):
        def resetCal():
            self.logger.debug(f'Resetting calendar "{self.name}" now after a timeout of {format(self.interval, ".2f")} seconds.')
            self.cal_text = None
            self._startTimer() # re-start timer

        self._stopTimer()
        self._timer = Timer(interval=float(self.interval), function=resetCal)
        self._timer.start()
        return self

    def isCached(self):
        return type(self.cal_text) is str
    
    def _getCalText(self):
        """This is a synchronized method.
        """
        self.semaphore.acquire()
        try:
            if not self.isCached():
                # Then we have to re-fetch this calendar.
                self.logger.debug(f'Downloading events for calendar "{self.name}".')
                res = http.get(url=self.url)
                if res.status_code != 200:
                    raise Exception(f'Cannot fetch ical, status={res.status_code}')
                self.cal_text = res.text
        finally:
            self.semaphore.release()
        
        return self.cal_text
    
    def getEvents(self) -> list[Event]:
        cal = Calendar.from_ical(self._getCalText())

        events = []

        for event in cal.walk("VEVENT"):
            end = event.get('dtend')
            if end:
                copied_event = Event()
                copied_event.add(name='X-CALENDARNAME', value=self.name)
                if 'RRULE' in event:
                    copied_event.add(name='X-ISRECURRENT', value=True)
                
                for attr in event:
                    if type(event[attr]) is list:
                        for element in event[attr]:
                            copied_event.add(attr, element)
                    else:
                        copied_event.add(attr, event[attr])
                
                events.append(copied_event)
        
        return events
    
    def getTodos(self) -> list[Todo]:
        cal = Calendar.from_ical(self._getCalText())

        todos = []

        for todo in cal.walk('VTODO'):
            copied_todo = Todo()
            copied_todo.add(name='X-CALENDARNAME', value=self.name)

            for attr in todo:
                if type(todo[attr]) is list:
                    for element in todo[attr]:
                        copied_todo.add(attr, element)
                else:
                    copied_todo.add(attr, todo[attr])
            
            todos.append(copied_todo)
        
        return todos



class Weekday:
    def __init__(self, month, week, day, weekday, before_today, is_today):
        self.month = month
        self.week = week
        self.day = day
        self.weekday = weekday
        self.before_today = before_today
        self.is_today = is_today
        self.after_today = not(before_today or is_today)
        self.events = []
    
    def addEvents(self, evts):
        for evt in evts:
            self.events.append(evt)
        return self
    
    def dict(self):
        return dict((key, value) for key, value in self.__dict__.items() if not callable(value) and not key.startswith('__'))
    
    def __json__(self):
        return jsons.dumps(obj=self.dict())
    
    def __str__(self):
        return self.__json__()



class CalendarMerger:

    def __init__(self, cal_config=None):
        self.merged_evt: Calendar = None
        self.merged_todo: Calendar = None

        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self.calendars: dict[str, IntervalCalendar] = {}
        if not cal_config is None:
            for conf in cal_config['merge']:
                self.addCalendar(IntervalCalendar(**conf))
    
    def addCalendar(self, intervalCal: IntervalCalendar):
        self.logger.debug(f'Adding IntervalCalendar "{intervalCal.name}"')
        self.calendars[intervalCal.name] = intervalCal
        return self
    
    def getMergedCalendar(self, events=True) -> Calendar:
        if not all([cal.isCached() for cal in self.calendars.values()]):
            self.merged_evt = None
            self.merged_todo = None

        if events:
            if type(self.merged_evt) is Calendar:
                return self.merged_evt
        else:
            if type(self.merged_todo) is Calendar:
                return self.merged_todo
        
        c = Calendar()
        c.add('prodid', '-//icalcombine//NONSGML//EN')
        c.add('version', '2.0')

        for cal in self.calendars.values():
            items = cal.getEvents() if events else cal.getTodos()
            for item in items:
                c.add_component(item)
        
        if events:
            self.merged_evt = c
        else:
            self.merged_todo = c
        return c
    
    def todosBetween(self, start, stop, include_indefinite=True, include_overdue_undone=True) -> list[DataEvent]:
        todos = []

        for item in self.getMergedCalendar(events=False).subcomponents:
            todo = DataEvent.fromVtodo(item)
            if todo.is_complete:
                continue

            cal = self.calendars.get(todo.cal_name)
            # The end of a VTODO describes when it's due.
            # Often, VTODOs don't have a start date.
            # Sometimes, they don't have an end date either,
            # which makes them indefinite.
            indef_tz = pytz.timezone(cal.tz_indef)
            has_start = type(todo.start) is datetime
            if has_start and todo.start.tzinfo is None:
                todo.start = indef_tz.localize(todo.start)
            has_end = type(todo.end) is datetime
            if has_end and todo.end.tzinfo is None:
                todo.end = indef_tz.localize(todo.end)
            
            point: datetime = todo.end if has_end else todo.start

            is_indef = (not has_start) and (not has_end)
            is_overdue_undone = type(point) is datetime and not todo.is_complete and point < start

            if is_indef:
                if include_indefinite:
                    todos.append(todo)
            elif is_overdue_undone:
                if include_overdue_undone:
                    todos.append(todo)
            else:
                if has_start ^ has_end:
                    if point >= start and point <= stop:
                        todos.append(todo)
                elif todo.start >= start and todo.end <= stop:
                    todos.append(todo)
        
        return todos

    def eventsBetween(self, start, stop) -> list[DataEvent]:
        return list(map(
            lambda vevt: DataEvent.fromVevent(vevt),
            of(self.getMergedCalendar(events=True)).between(start, stop)))
    
    def itemsToday(self, events=True, add_days=0) -> list[DataEvent]:
        """
        Returns the items of a single day. If add days is > 0,
        returns the items of a single n days in the future.
        """
        this_tz = datetime.now().astimezone().tzinfo
        today = datetime.now(tz=this_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        # note that eventsBetween is including the end
        tomorrow = today + timedelta(days=1) - timedelta(microseconds=1)

        if add_days != 0:
            today = today + timedelta(days=add_days)
            tomorrow = tomorrow + timedelta(days=add_days)

        if events:
            return self.eventsBetween(start=today, stop=tomorrow)
        else:
            return self.todosBetween(start=today, stop=tomorrow)

    
    def eventsToday(self, add_days=0) -> list[DataEvent]:
        return self.itemsToday(events=True, add_days=add_days)
    
    def todosToday(self, add_days=0) -> list[DataEvent]:
        return self.itemsToday(events=False, add_days=add_days)
    
    def weekdayItems(self, num_weeks=4, start_dt: datetime=None) -> list[Weekday]:
        this_tz = datetime.now().astimezone().tzinfo

        today = datetime.now(tz=this_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        begin = today
        if not start_dt is None:
            begin = start_dt.replace(tzinfo=this_tz, hour=0, minute=0, second=0, microsecond=0)

        weekdays = []

        while begin.isoweekday() > 1:
            # today is NOT monday, let's go back and find the dates before
            begin = begin - timedelta(days=1)
        
        for i in range(int(num_weeks * 7)):
            wd = Weekday(month=begin.month, week=begin.isocalendar().week, day=begin.day, weekday=begin.isoweekday(), before_today=begin < today, is_today=begin.month == today.month and begin.day == today.day)

            wd.addEvents(self.eventsBetween(
                start=begin, stop=begin + timedelta(days=1) - timedelta(microseconds=1)))
            wd.addEvents(self.todosBetween(
                include_indefinite=False, # Here we need concrete todos!
                start=begin, stop=begin + timedelta(days=1) - timedelta(microseconds=1)))

            weekdays.append(wd)
            
            begin = begin + timedelta(days=1)
        
        return weekdays

    def __str__(self):
        cal_evts = self.getMergedCalendar(events=True)
        cal_todo = self.getMergedCalendar(events=False)

        # Create a merged calendar with events AND todos:
        for comp in cal_todo.subcomponents:
            cal_evts.add_component(comp)
        
        return cal_evts.to_ical(sorted=True)
    
    def apiCal(self):
        return self.__str__(), 200, {'Content-Type': 'text/calendar; charset=utf-8'}


