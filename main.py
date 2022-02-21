from src.Configurator import Configurator


c = Configurator.fromJson(path='config.json')
c.setupCalendar()
c.setupStateMachines()
c.setupBtnLedControl()
c.startApi(blocking=False)
c.initStateMachines()
