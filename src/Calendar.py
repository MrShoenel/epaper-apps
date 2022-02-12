import sys
import datetime

import pytz
import requests
from icalendar import Calendar, Event


now = datetime.datetime.utcnow()
now.replace(tzinfo=pytz.utc)
today = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).date()


class CalendarApp:

    def __init__(self):
        c = Calendar()
        c.add('prodid', '-//icalcombine//NONSGML//EN')
        c.add('version', '2.0')
        self.calendar = c


    def addCalendar(self, url):
        req = requests.get(url)
        if req.status_code != 200:
            raise Exception(f'Cannot fetch ical, status={req.status_code}')

        cal = Calendar.from_ical(req.text)
        for event in cal.walk("VEVENT"):
            end = event.get('dtend')
            if end:
                if hasattr(end.dt, 'date'):
                    date = end.dt.date()
                else:
                    date = end.dt
                if date >= today or 'RRULE' in event:
                    copied_event = Event()
                    for attr in event:
                        if type(event[attr]) is list:
                            for element in event[attr]:
                                copied_event.add(attr, element)
                        else:
                            copied_event.add(attr, event[attr])
                    self.c.add_component(copied_event)

        return self
