import os
from PIL import Image
from src.CustomFormatter import CustomFormatter

if os.name == 'posix':
    from src.epd7in5b_V2 import EPD


class ePaper():
    def __init__(self):
        self.epaper = EPD()
        self._inited = False
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    @staticmethod
    def display(black_img: Image, red_img):
        e = ePaper()
        e._display(black_img=black_img, red_img=red_img, clear_before=True, sleep_after=True)
        
        return None
    
    def __del__(self):
        self.epaper.init()
        self.epaper.Clear()
        self.epaper.sleep()
    
    def _display(self, black_img: Image, red_img: Image, clear_before: bool=False, sleep_after: bool=True):
        was_inited = self._inited
        if not self._inited:
            self.epaper.init()
            self._inited = True
        
        if not was_inited or clear_before:
            self.epaper.Clear()
        
        self.epaper.display(
            imageblack=self.epaper.getbuffer(black_img),
            imagered=self.epaper.getbuffer(red_img))
        
        if sleep_after:
            self.logger.debug('Sending e-paper display to sleep.')
            self.epaper.sleep()
        
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

