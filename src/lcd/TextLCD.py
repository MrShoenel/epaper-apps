from threading import Semaphore
from rpi_lcd import LCD



class TextLCD:
    def __init__(self, cols: int=16, rows: int=2):
        self.cols = cols
        self.rows = rows
        self._lcd = LCD()
        self._semaphore = Semaphore(value=1)

    def __del__(self):
        del self._semaphore
    
    def text(self, line: str, row: int=1):
        """
        This method is thread-safe, such that the text on the LCD
        never gets messed up.
        """
        if len(line) != self.cols or row < 1 or row > self.rows:
            raise Exception(f'The line must have an exact length of {self.cols} characters, and the row must >= 1 and <= {self.rows}.')
        self._semaphore.acquire()
        self._lcd.text(line, row)
        self._semaphore.release()

        return self
    
    def clear(self):
        self._lcd.clear()
        return self