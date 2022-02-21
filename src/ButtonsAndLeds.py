from src.CustomFormatter import CustomFormatter
from events import Events
from typing import Dict, Set
from datetime import datetime
import RPi.GPIO as GPIO
import asyncio
import atexit



class Button:
    def __init__(self, pin: int, name: str, bounce_time: float=1):
        self.pin = pin
        self.name = name
        self.bounce_time = bounce_time
        self.last_press: float = 0

class Led:
    def __init__(self, pin: int, name: str, burn_for: float=1.5):
        self.pin = pin
        self.name = name
        self.burn_for = burn_for


class ButtonsAndLeds(Events):

    def __init__(self):
        super().__init__(events=('on_button', ))
        self._buttons: Set[Button] = set()
        self._leds: Set[Led] = set()

        GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
        atexit.register(self.cleanup)
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

    def __del__(self):
        self.cleanup()

    def _triggerButton(self, btn: Button):
        now = datetime.now().timestamp()
        if (now - btn.last_press) > btn.bounce_time:
            self.logger.debug(f'Button {btn.name} (pin={btn.pin}) was pressed.')
            btn.last_press = now
            self.on_button(btn)
        return self

    async def burnLed(self, led: Led, burn_for: float=None):
        duration = burn_for if type(burn_for) is float else led.burn_for
        self.logger.debug('Burning LED {led.name} (pin={led.pin}) for {duration} seconds.')

        GPIO.output(led.pin, GPIO.HIGH)
        await asyncio.sleep(delay=duration)
        GPIO.output(led.pin, GPIO.LOW)
        return self
    
    def cleanup(self):
        self.logger.debug('Cleaning up registered buttons and LEDs.')
        if len(self._buttons) > 0:
            GPIO.cleanup(list(map(lambda btn: btn.pin, self._buttons)))
        if len(self._leds) > 0:
            GPIO.cleanup(list(map(lambda led: led.pin, self._leds)))

        return self

    def addButton(self, pin: int, name: str, bounce_time: float) -> Button:
        if pin in map(lambda btn: btn.pin, self._buttons):
            raise Exception(f'There is already a button on pin {pin}.')

        btn = Button(pin=pin, name=name, bounce_time=bounce_time)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        # Argument 'bouncetime' does not work reliably in the following set up call.
        GPIO.add_event_detect(gpio=pin, edge=GPIO.RISING, callback=lambda _: self._triggerButton(btn))
        self._buttons.add(btn)

        return btn
    
    def addLed(self, pin: int, name: str, burn_for: float) -> Led:
        if pin in map(lambda led: led.pin, self._leds):
            raise Exception(f'There is already an LED on pin {pin}.')

        led = Led(pin=pin, name=name, burn_for=burn_for)
        GPIO.setup(pin, GPIO.OUT)
        self._leds.add(led)

        return led


if __name__ == "__main__":

    ctrl = ButtonsAndLeds()

    blue = ctrl.addButton(35, 'blue', 2.5)
    yell = ctrl.addButton(36, 'yellow', 2.5)

    led_blue = ctrl.addLed(37, 'blue', 1)
    led_yell = ctrl.addLed(38, 'yellow', 1)


    asyncio.run(ctrl.burnLed(led_blue))
    asyncio.run(ctrl.burnLed(led_yell))


    def btnCallback(btn: Button):
        print(btn.__dict__)
        if btn.name == 'blue':
            asyncio.run(ctrl.burnLed(led_blue))
        elif btn.name == 'yellow':
            asyncio.run(ctrl.burnLed(led_yell))

    ctrl.on_button += btnCallback

    input('Press enter to quit.')

