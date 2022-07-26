from concurrent.futures import ThreadPoolExecutor
import logging
from logging import LogRecord
from typing_extensions import Self
from events import Events
from threading import Lock
from os.path import exists, getsize



seh_pool = ThreadPoolExecutor(max_workers=1)


class FileLogger:
    def __init__(self, formatter: logging.Formatter, file: str, maxLines: int) -> None:
        self.formatter = formatter
        self.file = file
        self.maxLines = maxLines
        self.lock = Lock()

    def _trimFileBegin(self) -> Self:
        lines = open(self.file).readlines()
        if len(lines) > self.maxLines:
            lines = lines[(len(lines) - self.maxLines):]
            with open(file=self.file, mode='w') as f:
                f.truncate()
                f.writelines(lines)

        return self

    
    def addRecord(self, record: LogRecord) -> Self:
        locked = False
        try:
            locked = self.lock.acquire()
            newline = '\n' if exists(self.file) and getsize(self.file) > 0 else ''
            with open(file=self.file, mode='a') as f:
                f.write(f'{newline}{self.formatter.format(record).strip()}')
            return self._trimFileBegin()
        finally:
            if locked:
                self.lock.release()
        


class StreamEventHandler(logging.StreamHandler, Events):
    def __init__(self, stream=None, fileLogger: FileLogger=None):
        logging.StreamHandler.__init__(self=self, stream=stream)
        Events.__init__(self=self, events=('onHandle'))
        self.fileLogger = fileLogger
        
        def handler(record: LogRecord):
            self.onHandle(record)
        
        if isinstance(fileLogger, FileLogger):
            temp = handler
            def handler(record: LogRecord):
                temp(record=record)
                self.fileLogger.addRecord(record)
        
        self._handler = handler

    def handle(self, record: LogRecord) -> bool:
        seh_pool.submit(lambda: self._handler(record=record))
        return super().handle(record)


class CustomFormatter(logging.Formatter):

    use_log_level = logging.INFO

    handler = None

    file_logger = None

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    green = "\x1b[32;20m"
    magenta = "\x1b[35;20m"
    cyan = "\x1b[36;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    #format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    format = "[%(asctime)s][%(name)s]: %(message)s"

    FORMATS = {
        logging.DEBUG: green + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
    
    @staticmethod
    def setLogFile(file: str, maxLines: int=1000):
        CustomFormatter.file_logger = FileLogger(formatter=CustomFormatter(), file=file, maxLines=maxLines)

    @staticmethod
    def setLevel(level: int=logging.DEBUG):
        logging.getLogger().setLevel(level=level)
        CustomFormatter.use_log_level = level

    @staticmethod
    def getLoggerFor(name: str):
        if CustomFormatter.handler is None:
            consHand = StreamEventHandler(fileLogger=CustomFormatter.file_logger) # logging.StreamHandler()
            consHand.setLevel(level=CustomFormatter.use_log_level)
            consHand.setFormatter(CustomFormatter())
            CustomFormatter.handler = consHand

        CustomFormatter.handler.setLevel(level=CustomFormatter.use_log_level)
        logger = logging.getLogger(name=name)
        logger.addHandler(CustomFormatter.handler)
        logger.setLevel(level=CustomFormatter.use_log_level)
        return logger
