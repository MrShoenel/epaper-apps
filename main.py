import os
from src.Configurator import Configurator


c = Configurator.fromJson(path='config.json')
c.setupCalendar()
c.startApi(blocking=False)
c.setupStateMachines()
if os.name == 'posix':
    c.setupBtnLedControl()
    c.initStateMachines()
c.waitApi()
