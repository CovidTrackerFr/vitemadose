import json
from pathlib import Path
from typing import Optional

from utils.vmd_logger import get_logger

CONFIG_DATA = {}

logger = get_logger()


def get_config() -> dict:
    global CONFIG_DATA
    if not CONFIG_DATA:
        try:
            CONFIG_DATA = json.loads(Path("config.json").read_text(encoding='utf8'))
        except (OSError, ValueError):
            logger.exception("Unable to load configuration file.")
    return CONFIG_DATA


def get_conf_inputs() -> Optional[dict]:
    return get_config().get("inputs", {})


def get_conf_outputs() -> Optional[dict]:
    return get_config().get("outputs", {})


def get_conf_outstats() -> Optional[dict]:
    return get_conf_outputs().get("stats", {})


def get_conf_platform(platform: str) -> dict:
    if not get_config().get("platforms"):
        logger.error("Unknown ’platforms’ key in configuration file.")
        exit(1)
    platform_conf = get_config().get("platforms").get(platform)
    if not platform_conf:
        logger.error(f"Unknown ’{platform}’ platform in configuration file.")
        exit(1)
    return platform_conf
