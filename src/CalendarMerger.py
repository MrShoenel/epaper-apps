import os
import datetime
import pytz
import requests
import jsons
from os.path import exists
from time import sleep
from dateutil import tz
from typing import Any, Callable, Union
from src.CustomFormatter import CustomFormatter
from datetime import date, datetime, timedelta
from icalendar import Calendar, Event, Todo
from recurring_ical_events import of
from src.SelfResetLazy import SelfResetLazy




def ifelse(cond, fnTrue: Callable[[], Any], iffalse):
    if cond:
        return fnTrue()
    return iffalse

def to_datetime(dt):
    if type(dt) is date:
        return datetime.combine(dt, datetime.min.time())
    return dt

def compare_datetime(a, b):
    a = to_datetime(a).astimezone(pytz.utc)
    b = to_datetime(b).astimezone(pytz.utc)
    if a < b:
        return -1
    elif a == b:
        return 0
    return 1


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

    def __init__(self, name: str, url: str, interval: int, data_folder: str, tz_indef: datetime.tzinfo=None):
        self.name = name
        self.url = url
        self.interval = interval
        self.data_folder = data_folder
        self.tz_indef = tz_indef

        self.logger = CustomFormatter.getLoggerFor(f'{self.__class__.__name__}({name})')

        def getCalText():
            # Then we have to re-fetch this calendar.
            self.logger.debug(f'Downloading events for calendar "{self.name}".')
            ical_file = f'{self.data_folder}{os.sep}{self.name}.ical'
            retries = 10
            while retries > 0:
                retries -= 1
                try:
                    res = requests.get(url=self.url)
                    if res.status_code == 200:
                        # Buffer this calendar to disk:
                        with open(file=ical_file, mode='w', encoding='utf-8') as fp:
                            print(res.text, file=fp)
                        return res.text
                    sleep(secs=3.0)
                except Exception:
                    pass # Explicitly ignore, as we have our retries.

            self.logger.error(f'Cannot fetch ical for "{self.name}".')

            if exists(ical_file):
                # Try to read previously buffered file:
                with open(file=ical_file, mode='r', encoding='utf-8') as fp:
                    temp = fp.read()
                    self.logger.warn('Returning cached (potentially) old calendar.')
                    return temp
            else:
                return '' # return empty text, so the others may work.
        
        def destroyCalText(cal: str):
            self.logger.debug(f'Resetting calendar "{self.name}" now after a timeout of {format(self.interval, ".2f")} seconds.')

        self.cal_text: SelfResetLazy[str] = SelfResetLazy(
            fnCreateVal=getCalText, fnDestroyVal=destroyCalText, resetAfter=float(interval), resource_name=f'Cal:{self.name}')

    @property
    def isCached(self):
        return self.cal_text.hasValue
    
    @staticmethod
    def filterEvents(events: list[Event], cal_name: str=None, min_date: datetime=None):
        filtered = []

        for event in events:
            if not event.has_key('dtend'):
                continue

            end = event.get('dtend')
            copied_event = Event()
            if type(cal_name) is str:
                copied_event.add(name='X-CALENDARNAME', value=cal_name)

            if 'RRULE' in event:
                copied_event.add(name='X-ISRECURRENT', value=True)
            elif type(min_date) is datetime and compare_datetime(end.dt, min_date) == -1:
                # Not recurring and too old, skip:
                continue

            for attr in event:
                if type(event[attr]) is list:
                    for element in event[attr]:
                        copied_event.add(attr, element)
                else:
                    copied_event.add(attr, event[attr])
            
            filtered.append(copied_event)
        
        return filtered
    
    def getEvents(self, min_date: datetime=None) -> list[Event]:
        cal: Calendar = Calendar.from_ical(self.cal_text.value)

        return IntervalCalendar.filterEvents(events=cal.walk('VEVENT'), cal_name=self.name, min_date=min_date)
    
    @staticmethod
    def filterTodos(todos: list[Todo], cal_name: str=None, min_date: datetime=None, include_indef: bool=True, include_undone: bool=True) -> list[Todo]:
        filtered = []
        
        for todo in todos:
            is_done = todo.get('status') == 'COMPLETED'
            if is_done:
                continue # Skip done tasks

            copied_todo = Todo()
            if type(cal_name) is str:
                copied_todo.add(name='X-CALENDARNAME', value=cal_name)

            if not include_undone:
                has_start = todo.has_key('dtstart') # most tasks have 'due' or no date
                has_due = todo.has_key('due')
                is_indef = not has_start and not has_due

                if is_indef:
                    if not include_indef and not (include_undone and not is_done):
                        continue
                elif type(min_date) is datetime:
                    start = todo.get('dtstart').dt
                    due = todo.get('due').dt
                    point = start if not type(due) is datetime else due
                    if type(start) is datetime and type(due) is datetime:
                        point = max(start, due)
                    if compare_datetime(point, min_date) == -1:
                        continue # Too old this one

            for attr in todo:
                if type(todo[attr]) is list:
                    for element in todo[attr]:
                        copied_todo.add(attr, element)
                else:
                    copied_todo.add(attr, todo[attr])
            
            filtered.append(copied_todo)
        
        return filtered
    
    def getTodos(self, min_date: datetime=None, include_indef: bool=True, include_undone: bool=True) -> list[Todo]:
        cal: Calendar = Calendar.from_ical(self.cal_text.value)

        return IntervalCalendar.filterTodos(todos=cal.walk('VTODO'), cal_name=self.name, min_date=min_date, include_indef=include_indef, include_undone=include_undone)



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

    def __init__(self, data_folder: str, cal_config=None):
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

        self.calendars: dict[str, IntervalCalendar] = {}
        for conf in cal_config['merge']:
            self.addCalendar(IntervalCalendar(data_folder=data_folder, **conf))
        
        self.include_indefinite = cal_config['tasks']['include_indefinite']
        self.include_overdue_undone = cal_config['tasks']['include_overdue_undone']

        def merge_calendars(events: bool=True) -> Union[list[Event], list[Todo]]:
            items: list[DataEvent] = []
            for cal in self.calendars.values():
                if events:
                    items += cal.getEvents()
                else:
                    items += cal.getTodos(include_indef=self.include_indefinite, include_undone=self.include_overdue_undone)
            return items


        self._merged_evts: SelfResetLazy[list[Event]] = SelfResetLazy(resource_name='merged_events', fnCreateVal=lambda: merge_calendars(events=True), resetAfter=None)
        self._merged_todos: SelfResetLazy[list[Todo]] = SelfResetLazy(resource_name='merged_todos', fnCreateVal=lambda: merge_calendars(events=False), resetAfter=None)
    
    def addCalendar(self, intervalCal: IntervalCalendar):
        self.logger.debug(f'Adding IntervalCalendar "{intervalCal.name}"')
        self.calendars[intervalCal.name] = intervalCal
        return self

    def _getMergedItems(self, events: bool=True) -> Union[list[Event], list[Todo]]:
        if not all([cal.isCached for cal in self.calendars.values()]):
            self._merged_evts.unsetValue()
            self._merged_todos.unsetValue()
        
        if events:
            return self._merged_evts.value
        return self._merged_todos.value

    def getMergedCalendar(self, events: bool=True, min_date: datetime=None) -> Calendar:
        c = Calendar()
        c.add('prodid', '-//icalcombine//NONSGML//EN')
        c.add('version', '2.0')

        items: Union[list[Event], list[Todo]] = []
        if events:
            items = IntervalCalendar.filterEvents(events=self._getMergedItems(events=True), min_date=min_date)
        else:
            items = IntervalCalendar.filterTodos(todos=self._getMergedItems(events=False), min_date=min_date, include_indef=self.include_indefinite, include_undone=self.include_overdue_undone)
        
        for item in items:
            c.add_component(item)
        
        return c

    def todosBetween(self, start, stop, include_indefinite=True, include_overdue_undone=True) -> list[DataEvent]:
        todos = []

        for item in self.getMergedCalendar(events=False, min_date=start).subcomponents:
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
            is_overdue_undone = type(point) is datetime and not todo.is_complete and compare_datetime(point, start) == -1

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
            of(self.getMergedCalendar(events=True, min_date=start)).between(start, stop)))
    
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
        
        for _ in range(int(num_weeks * 7)):
            wd = Weekday(month=begin.month, week=begin.isocalendar().week, day=begin.day, weekday=begin.isoweekday(), before_today=compare_datetime(begin, today) == -1, is_today=begin.month == today.month and begin.day == today.day)

            wd.addEvents(self.eventsBetween(
                start=begin, stop=begin + timedelta(days=1) - timedelta(microseconds=1)))
            wd.addEvents(self.todosBetween(
                include_indefinite=False, # Here we need concrete todos!
                start=begin, stop=begin + timedelta(days=1) - timedelta(microseconds=1)))

            weekdays.append(wd)
            
            begin = begin + timedelta(days=1)
        
        return weekdays

    def __str__(self):
        items: Union[list[Event], list[Todo]] = []

        items += self._getMergedItems(events=True)
        items += self._getMergedItems(events=False)

        c = Calendar()
        c.add('prodid', '-//icalcombine//NONSGML//EN')
        c.add('version', '2.0')

        # Create a new merged calendar with events AND todos:
        for item in items:
            c.add_component(item)

        return c.to_ical(sorted=True)
    
    def apiCal(self):
        return self.__str__(), 200, {'Content-Type': 'text/calendar; charset=utf-8'}


