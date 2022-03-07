import os
from src.Configurator import Configurator


c = Configurator.fromJson(path='config.json')
c.setupCalendar()
if c.useScreenshotService:
    c.setupScreenshotService()
    c.setupScreenIntervals()
c.setupUserscreens()
c.setupNews()
c.startApi(blocking=False)
if c.calibrateEpaperOnStart:
    c.calibrateEpaper()
c.setupStateMachines()
if os.name == 'posix':
    c.setupBtnLedControl()
    c.initStateMachines()
c.waitApi()
