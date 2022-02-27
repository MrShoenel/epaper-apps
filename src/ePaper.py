import os
from PIL import Image
from src.CustomFormatter import CustomFormatter
from threading import Timer
from random import uniform

if os.name == 'posix':
    from src.epd7in5b_V2 import EPD, epdconfig


class ePaper():
    def __init__(self):
        self.epaper = EPD()
        self._inited = False
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    @staticmethod
    def display(black_img: Image, red_img):
        e = ePaper()
        e._display(black_img=black_img, red_img=red_img, clear_before=None, sleep_after=False)
        del e
        return None
    
    def __del__(self):
        try:
            self.epaper.sleep()
        except Exception as e:
            self.logger.warning(f'The e-paper had an exception while attempting to sleep: ' + str(e))
    
    def _display(self, black_img: Image, red_img: Image, clear_before: bool=False, sleep_after: bool=True, cancel_after: float=60.0):
        def interrupt():
            self.logger.debug('Forcefully interrupting the e-paper.')
            had_ex = False
            try:
                epdconfig.module_exit()
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
            was_inited = self._inited
            if not self._inited:
                self.epaper.init()
                self._inited = True
            
            if uniform(0,1) > 2/3:
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
            self._display(black, white)
            self._display(black, white)
            self._display(white, black)
            self._display(white, white)

        self.logger.info(f'Calibrated e-paper display using {cycles} cycles.')
        return self

