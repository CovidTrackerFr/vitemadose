import json
import traceback
from typing import Optional

from utils.vmd_logger import get_logger

CONFIG_DATA = {}

logger = get_logger()


def get_config() -> Optional[dict]:
    global CONFIG_DATA
    if not CONFIG_DATA:
        file = open("config.json")
        try:
            CONFIG_DATA = json.loads(file.read())
        except:
            logger.error("Unable to load configuration file:")
            traceback.print_exc()
            exit(1)
        file.close()
    return CONFIG_DATA


def get_conf_inputs() -> Optional[dict]:
    return get_config().get("inputs", {})


def get_conf_outputs() -> Optional[dict]:
    return get_config().get("outputs", {})


def get_conf_outstats() -> Optional[dict]:
    return get_conf_outputs().get("stats", {})


def get_conf_platform(platform: str) -> Optional[dict]:
    if not get_config().get("platforms"):
        logger.error("Unknown ’platforms’ key in configuration file.")
        exit(1)
    platform_conf = get_config().get("platforms").get(platform)
    if not platform_conf:
        logger.error(f"Unknown ’{platform}’ platform in configuration file.")
        exit(1)
    return platform_conf
