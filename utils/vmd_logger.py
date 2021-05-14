import logging

from terminaltables import AsciiTable


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


def log_requests(request):
    logger = get_logger()
    if not request or not request.requests:
        logger.debug(f"{request.internal_id} requests -> No requests made.")
        return
    requests = ""
    total_requests = 0
    for type, value in request.requests.items():
        requests += f", {type}({value})"
        total_requests += value
    logger.debug(f"{request.internal_id} requests -> Total({total_requests}){requests}")


def log_platform_requests(centers):
    logger = get_logger()
    platforms = {}

    print("Requests count:")
    # Not fan of the way I do this
    # maybe python has builtin ways to do this in an easier way
    if not centers:
        logger.info(f"No centers found.")
        return
    for center in centers:
        platform = center.plateforme
        if platform not in platforms:
            platforms[platform] = {}
        if not center.request_counts:
            continue
        for request_type, request_count in center.request_counts.items():
            if request_type not in platforms[platform]:
                platforms[platform][request_type] = 0
            platforms[platform][request_type] += request_count
    if not platforms:
        logger.info("No platforms found.")
    datatable_keys = ["Platform", "Total"]
    datatable_keys.extend(list(set([subkey for sdict in platforms.values() for subkey in sdict])))
    datatable = [datatable_keys]
    for platform, requests in platforms.items():
        data = [platform]
        for key in datatable_keys:
            if key == "Total":
                data.append(sum([req_count for req_count in requests.values()]))
            elif key != "Platform":
                data.append(requests.get(key, 0))
        datatable.append(data)

    table = AsciiTable(datatable)
    print(table.table)
