from src.CustomFormatter import CustomFormatter
from events import Events
from typing import Dict, Set
from datetime import datetime
from time import sleep
from concurrent.futures import ThreadPoolExecutor, Future
import RPi.GPIO as GPIO
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
        # Used to asynchronously fire buttons, and LEDs
        self._tpe = ThreadPoolExecutor(max_workers=2)

        atexit.register(self.cleanup)
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

    def __del__(self):
        self.cleanup()

    def _triggerButton(self, btn: Button):
        now = datetime.now().timestamp()
        if (now - btn.last_press) > btn.bounce_time and not self._tpe._shutdown:
            def temp():
                self.logger.debug(f'Button {btn.name} (pin={btn.pin}) was pressed.')
                self.on_button(btn)
            self._tpe.submit(temp)
        btn.last_press = now

        return self
    
    def blinkLed(self, led: Led, freq: int=10, duration: float=2.0) -> Future:
        def temp(duration):
            on = True
            while duration > 0:
                cycle = 1.0/freq
                if on:
                    GPIO.output(led.pin, GPIO.HIGH)
                    sleep(cycle)
                    GPIO.output(led.pin, GPIO.LOW)
                else:
                    sleep(cycle)
                duration -= cycle
                on = not on
            GPIO.output(led.pin, GPIO.LOW) # finally

        if self._tpe._shutdown:
            f = Future()
            f.cancel()
            return f
        else:
            return self._tpe.submit(temp, self)

    def burnLed(self, led: Led, burn_for: float=None) -> Future:
        def temp():
            duration = burn_for if type(burn_for) is float else led.burn_for
            self.logger.debug(f'Burning LED {led.name} (pin={led.pin}) for {duration} seconds.')

            GPIO.output(led.pin, GPIO.HIGH)
            sleep(duration)
            GPIO.output(led.pin, GPIO.LOW)
        
        if self._tpe._shutdown:
            f = Future()
            f.cancel()
            return f
        else:
            return self._tpe.submit(temp)
    
    def cleanup(self):
        self.logger.debug('Cleaning up registered buttons and LEDs.')
        if len(self._buttons) > 0:
            for btn in self._buttons:
                GPIO.remove_event_detect(btn.pin)
                GPIO.cleanup(btn.pin)
        if len(self._leds) > 0:
            GPIO.cleanup(list(map(lambda led: led.pin, self._leds)))
        
        self._buttons.clear()
        self._leds.clear()

        self._tpe.shutdown()

        return self

    def addButton(self, pin: int, name: str, bounce_time: float) -> Button:
        if pin in map(lambda btn: btn.pin, self._buttons):
            raise Exception(f'There is already a button on pin {pin}.')

        btn = Button(pin=pin, name=name, bounce_time=bounce_time)
        self.logger.debug(f'Adding button on GPIO {pin}.')
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        # Argument 'bouncetime' does not work reliably in the following set up call.
        GPIO.add_event_detect(gpio=pin, edge=GPIO.RISING, callback=lambda _: self._triggerButton(btn))
        self._buttons.add(btn)

        return btn
    
    def addLed(self, pin: int, name: str, burn_for: float) -> Led:
        if pin in map(lambda led: led.pin, self._leds):
            raise Exception(f'There is already an LED on pin {pin}.')

        led = Led(pin=pin, name=name, burn_for=burn_for)
        self.logger.debug(f'Adding LED on GPIO {pin}.')
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

