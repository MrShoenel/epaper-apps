import logging



class CustomFormatter(logging.Formatter):

    use_log_level = logging.INFO

    handler = None

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
    def setLevel(level: int=logging.DEBUG):
        logging.getLogger().setLevel(level=level)
        CustomFormatter.use_log_level = level

    @staticmethod
    def getLoggerFor(name: str):
        if CustomFormatter.handler is None:
            consHand = logging.StreamHandler()
            consHand.setLevel(level=CustomFormatter.use_log_level)
            consHand.setFormatter(CustomFormatter())
            CustomFormatter.handler = consHand

        CustomFormatter.handler.setLevel(level=CustomFormatter.use_log_level)
        logger = logging.getLogger(name=name)
        logger.addHandler(CustomFormatter.handler)
        logger.setLevel(level=CustomFormatter.use_log_level)
        return logger
