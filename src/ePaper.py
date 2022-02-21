from PIL import Image
from src.epd7in5b_V2 import EPD
from src.CustomFormatter import CustomFormatter


class ePaper():
    def __init__(self):
        self.epaper = EPD()
        self._inited = False
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def __del__(self):
        self.epaper.init()
        self.epaper.Clear()
        self.epaper.sleep()
    
    def display(self, black_img: Image, red_img: Image, clear_before: bool=False, sleep_after: bool=True):
        was_inited = self._inited
        if not self._inited:
            self.epaper.init()
            self._inited = True
        
        if not was_inited or clear_before:
            self.epaper.Clear()
        
        self.epaper.display(imageblack=black_img, imagered=red_img)
        
        if sleep_after:
            self.logger.debug('Sending e-paper display to sleep.')
            self.epaper.sleep()
        
        return self
    
    def calibrate(self, cycles=1):
        # Calibrates the display to prevent ghosting
        white = Image.new('1', (self.screenwidth, self.screenheight), 'white')
        black = Image.new('1', (self.screenwidth, self.screenheight), 'black')
        for _ in range(cycles):
            self.epd.display(black, white)
            self.epd.display(white, black)
            self.epd.display(white, white)
        self.logger.info(f'Calibrated e-paper display using {cycles} cycles.')
        return self

