import httpx
from httpx import TimeoutException
import json
import logging
import urllib.parse as urlparse

from datetime import datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs
from bs4 import BeautifulSoup

from scraper.mapharma import getReasons
from scraper.mapharma import getName
from scraper.mapharma import getProfiles
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = enable_logger_for_debug()

insee = {}
campagnes = {}

def parseAllZip():
    profiles = dict()
    with open("data/input/codepostal_to_insee.json", "r") as json_file:
        zips = json.load(json_file)
        for zip in zips.keys():
            logging.debug(f'Searching cp {zip}...')
            for profile in getProfiles(zip, DEFAULT_CLIENT):
                if zip not in profiles:
                    profiles[zip] = [] 
                profiles[zip].append(profile)
            if zip in profiles and len(profiles[zip]) > 0:
                logging.info(f'found {len(profiles[zip])} in cp {zip}')
    with open("data/input/mapharma.json", "w") as json_file:
        json.dump(profiles, json_file, indent = 4)

parseAllZip()