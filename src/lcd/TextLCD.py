import os
from typing import Dict
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
        self._last_lines: Dict[int, str] = {}
        for i in range(1, rows + 1):
            self._last_lines[i] = ''
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def text(self, line: str, row: int=1, force_rewrite: bool=False):
        """
        This method is thread-safe, such that the text on the LCD
        never gets messed up.
        Also, the line is not necessarily written to the LCD if it
        was previously buffered and force_rewrite is False.
        """
        if not force_rewrite and self._last_lines[row] == line:
            return self
        else:
            self._last_lines[row] = line

        if len(line) != self.cols or row < 1 or row > self.rows:
            self.logger.warn(f'The given line does not have a length of {self.cols}, but rather {len(line)}. The row must be >= 1 and <= {self.rows}, it was given as {row}. The line given was: "{line}"')
            line = line.ljust(self.cols)[0:self.cols]
        _semaphore.acquire()
        self._lcd.text(line, row)
        _semaphore.release()

        return self
    
    def clear(self):
        _semaphore.acquire()
        self._lcd.clear()
        _semaphore.release()
        return self
