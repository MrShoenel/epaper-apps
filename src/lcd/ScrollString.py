from typing import Callable


class BounceString:

    def __init__(self, strFn: Callable[[], str], width=16):
        self.fn = strFn
        self.width = width
        self.pos = 0
        self.b = width - len(strFn())
        self.r = True
    
    def reset(self):
        self.pos = 0
        return self

    def bounce(self, by=1):
        s = self.fn()
        if (self.width - len(s)) != self.b:
            # If the length changes, we start over.
            self.b = self.width - len(s)
            self.reset()
        
        large = len(s) > self.width
        
        o = self.b
        if large:
            o *= -1

        if self.r:
            if self.pos < o:
                self.pos += by
            if self.pos >= o:
                self.pos = o
                self.r = False
        else:
            if self.pos > 0:
                self.pos -= by
            if self.pos <= 0:
                self.pos = 0
                self.r = True

        if large:
            return s[self.pos:(self.pos + self.width)]

        return s.rjust(len(s) + self.pos).ljust(self.width)







class ScrollString:

    def __init__(self, strFn: Callable[[], str], width: int=16):
        self.fn = strFn
        self.pos = 0
        self.width = width
    
    def reset(self):
        self.pos = 0
        return self

    def scroll(self, by = 1):
        s = self.fn()
        if type(self.width) is int:
            s = s[0:self.width].ljust(self.width)
        self.pos = self.pos + by
        if self.pos >= len(s):
            self.pos = 0

        s = s[self.pos:len(s)] + s[0:self.pos]

        return s
