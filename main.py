import os
from src.Configurator import Configurator


c = Configurator.fromJson(path='config.json')
c.setupCalendar()
if c.useScreenshotService:
    c.setupScreenshotService()
    c.setupScreenIntervals()
c.startApi(blocking=False)
c.setupStateMachines()
if os.name == 'posix':
    c.setupBtnLedControl()
    c.initStateMachines()
    c.ctrl.switchLed(led=c.ctrl.getLed(name='led-green'), on=True)
c.waitApi()
