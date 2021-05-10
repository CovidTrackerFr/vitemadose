import logging
from typing import Dict


class CustomFormatter(logging.Formatter):
    grey: str = "\x1b[38;21m"
    yellow: str = "\x1b[33;21m"
    red: str = "\x1b[31;21m"
    bold_red: str = "\x1b[31;1m"
    reset: str = "\x1b[0m"
    format_pattern: str = "%(asctime)s | [%(levelname)s] %(message)s"

    FORMATS: Dict[int, str] = {
        logging.DEBUG: grey + format_pattern + reset,
        logging.INFO: grey + format_pattern + reset,
        logging.WARNING: yellow + format_pattern + reset,
        logging.ERROR: red + format_pattern + reset,
        logging.CRITICAL: bold_red + format_pattern + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def get_logger() -> logging.Logger:
    # create logger
    return logging.getLogger("scraper")


def enable_logger_for_production() -> logging.Logger:
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
