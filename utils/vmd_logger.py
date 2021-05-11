import logging


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s | [%(levelname)s] %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def get_logger():
    # create logger
    return logging.getLogger("scraper")


def enable_logger_for_production():
    logger = get_logger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(CustomFormatter())
        logger.addHandler(ch)

    return logger


def enable_logger_for_debug():
    # must be called after enable_logger_for_production(), otherwise it'll be partially overridden by it
    logger = get_logger()
    logger.setLevel(logging.DEBUG)

    # disable production "scraper" logger handler: all will be handled on root logger
    if logger.handlers:
        logger.handlers = []

    root_logger = logging.root
    root_logger.setLevel(logging.DEBUG)

    if not root_logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(CustomFormatter())
        root_logger.addHandler(ch)
