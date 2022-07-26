import os
from PIL import Image
from src.CustomFormatter import CustomFormatter
from threading import Timer

if os.name == 'posix':
    from src.epd7in5b_V2 import EPD


class ePaper():
    def __init__(self):
        self.epaper = EPD()
        self._inited = False
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    @staticmethod
    def display(black_img: Image, red_img, clear_before: bool=False):
        e = ePaper()
        e._display(black_img=black_img, red_img=red_img, clear_before=clear_before, sleep_after=False)
        # When 'e' is destructed, __del__() will make the display sleep.
        return None
    
    def __del__(self):
        try:
            self.logger.debug('Sending e-paper display to sleep.')
            self.epaper.sleep()
        except Exception as e:
            self.logger.warning(f'The e-paper had an exception while attempting to sleep: ' + str(e))
    
    def _display(self, black_img: Image, red_img: Image, clear_before: bool=False, sleep_after: bool=True, cancel_after: float=60.0):
        def interrupt():
            self.logger.debug('Forcefully interrupting the e-paper.')
            had_ex = False
            try:
                self.epaper.epdconfig.module_exit()
            except Exception as e:
                self.logger.warning('Forceful interruption of e-paper incurred an exception: ' + str(e))
                had_ex = True
            if not had_ex:
                self.logger.debug('Forceful interruption of e-paper did NOT incur an immediate exception.')
        
        timer: Timer = None
        if type(cancel_after) is float and cancel_after > 0:
            timer = Timer(interval=cancel_after, function=interrupt)
            timer.start()

        try:
            if not self._inited:
                self.epaper.init()
                self._inited = True
            
            if clear_before:
                self.logger.debug('Clearing e-paper display.')
                self.epaper.Clear()

            self.epaper.display(
                imageblack=self.epaper.getbuffer(black_img),
                imagered=self.epaper.getbuffer(red_img))

            if type(timer) is Timer and timer.is_alive():
                timer.cancel()

            if sleep_after:
                self.logger.debug('Sending e-paper display to sleep.')
                self.epaper.sleep()
        except Exception as e:
            self.logger.warning('Attempting to display an image on the e-paper triggered an exception: ' + str(e))
            raise e # re-throw this because it must be handled up the chain!
        finally:
            if type(timer) is Timer and timer.is_alive():
                timer.cancel()

        
        return self
    
    def calibrate(self, cycles=1):
        # Calibrates the display to prevent ghosting
        white = Image.new('1', (800, 480), 'white')
        black = Image.new('1', (800, 480), 'black')

        for _ in range(cycles):
            self._display(black_img=black, red_img=white, sleep_after=False)
            self._display(black_img=black, red_img=white, sleep_after=False)
            self._display(black_img=white, red_img=black, sleep_after=False)
            self._display(black_img=white, red_img=white, sleep_after=False)

        self.logger.info(f'Calibrated e-paper display using {cycles} cycle(s).')
        return self

