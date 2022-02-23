from math import ceil
from typing import Callable


class ProgressString:

    def __init__(self, strFn: Callable[[], str], width: int=16, num_dots: int=2, str100pFn: Callable[[], str]=None):
        self.strFn = strFn
        self.str100pFn = strFn if str100pFn is None else str100pFn
        self.width = width
        if width < 8:
            raise Exception('The minimum allowed with is 8.')
        self.num_dots = num_dots
        self._last_dots = 0
        self.progress = 0.0
        pass

    def generateProgressText(self, show_dots: bool=True, show_percent: bool=True) -> str:
        """
        Generates this format: <strFn><dots><percent>, where the string produced
        by the function is limited in with to accommodate the dots and percent.
        """
        is_done = 100 == ceil(self.progress * 100)
        fn = self.strFn if not is_done else self.str100pFn
        line = fn()[0:self.width].ljust(self.width)
        if show_dots and not is_done:
            preserve = self.num_dots + (3 if show_percent else 0) # Percent is 'xx%' (<100)
            self._last_dots %= (self.num_dots + 1)
            line = line[0:(self.width - preserve)] + (self._last_dots * '.').ljust(self.num_dots)
            self._last_dots += 1
        if show_percent:
            p_format = '{:3.0f}%' if is_done else '{:2.0f}%'
            percent = p_format.format(ceil(self.progress * 100))
            if is_done:
                # Leave a space when 100%
                line = line[0:(self.width - 5)] + ' '
            line += percent
        
        return line

    def generateProgressBar(self, symb: str='=') -> str:
        pCols = self.width - 2
        numUsed = int(ceil(self.progress * pCols))
        arrow = '>' if numUsed < pCols else ''

        return f'[{numUsed * "="}{arrow}{max(pCols - numUsed - 1, 0) * " "}]'


if __name__ == "__main__":
    from time import sleep
    ps = ProgressString(strFn=lambda: 'Loading Blafoo Baz', str100pFn=lambda: 'Done long Text Bla!')
    
    n = 25
    for i in range(0, n+1):
        ps.progress = i/n
        #print(ps.generateProgressBar() + ' -- ' + '{:1.2f}'.format(i/n) + ' -- ' + ps.generateProgressText())
        print(ps.generateProgressText())
        print(ps.generateProgressBar())
        sleep(0.25)

