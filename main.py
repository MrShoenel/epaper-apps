import os
from src.Configurator import Configurator


c = Configurator.fromJson(path='config.json')
c.setupCalendar()
c.setupStateMachines()
if os.name == 'posix':
    c.setupBtnLedControl()
    c.initStateMachines()
c.startApi(blocking=True) # If this is not blocking, the 'c' object will be collected!
