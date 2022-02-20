from typing import Callable


class BounceString:

    def __init__(self, strFn: Callable[[], str], width=16):
        self.fn = strFn
        self.width = width
        self.pos = 0
        self.b = width - len(strFn())
        self.r = True

    def bounce(self, by=1):
        if self.r:
            if self.pos < self.b:
                self.pos = self.pos + by
            if self.pos >= self.b:
                self.pos = self.b
                self.r = False
        else:
            if self.pos > 0:
                self.pos = self.pos - by
            if self.pos <= 0:
                self.pos = 0
                self.r = True

        s = self.fn()
        return s.rjust(len(s) + self.pos).ljust(self.width)






class ScrollString:

    def __init__(self, strFn: Callable[[], str]):
        self.fn = strFn
        self.str = None
        self.pos = 0


    def scroll(self, by = 1):
        s = self.fn()
        self.pos = self.pos + by
        if self.pos >= len(s):
            self.pos = 0

        s = s[self.pos:len(s)] + s[0:self.pos]

        return s
