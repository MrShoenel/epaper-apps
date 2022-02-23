import os
from src.CustomFormatter import CustomFormatter
from threading import Semaphore


_semaphore = Semaphore(value=1)



class TextLCD:
    def __init__(self, cols: int=16, rows: int=2):
        self.cols = cols
        self.rows = rows
        if os.name == 'posix':
            from rpi_lcd import LCD
            self._lcd = LCD()
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def text(self, line: str, row: int=1):
        """
        This method is thread-safe, such that the text on the LCD
        never gets messed up.
        """
        if len(line) != self.cols or row < 1 or row > self.rows:
            self.logger.warn(f'The given line does not have a length of {self.cols}, but rather {len(line)}. The row must be >= 1 and <= {self.rows}, it was given as {row}. The line given was: "{line}"')
        _semaphore.acquire()
        self._lcd.text(line, row)
        _semaphore.release()

        return self
    
    def clear(self):
        _semaphore.acquire()
        self._lcd.clear()
        _semaphore.release()
        return self
