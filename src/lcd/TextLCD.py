import os
from threading import Semaphore

if os.name == 'posix':
    from rpi_lcd import LCD


__semaphore = Semaphore(value=1)



class TextLCD:
    def __init__(self, cols: int=16, rows: int=2):
        self.cols = cols
        self.rows = rows
        self._lcd = LCD()
    
    def text(self, line: str, row: int=1):
        """
        This method is thread-safe, such that the text on the LCD
        never gets messed up.
        """
        if len(line) != self.cols or row < 1 or row > self.rows:
            raise Exception(f'The line must have an exact length of {self.cols} characters, and the row must >= 1 and <= {self.rows}.')
        __semaphore.acquire()
        self._lcd.text(line, row)
        __semaphore.release()

        return self
    
    def clear(self):
        self._lcd.clear()
        return self
