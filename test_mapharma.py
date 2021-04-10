import logging
import scraper

from datetime import datetime
from multiprocessing import Pool

from scraper.mapharma import centre_iterator as mapharma_centre_iterator
from scraper.mapharma import fetch_slots as mapharma_fetch_slots
from scraper.pattern.scraper_result import ScraperResult
from scraper.pattern.scraper_request import ScraperRequest
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug

logger = logging.getLogger('scraper')
today = datetime.now().strftime('%Y-%m-%d')
centres_scannes = 0
centres_trouves = 0

def mapharma_scrape(centre):
    global centres_scannes
    global centres_trouves
    vaccine_center = centre["nom"]
    com_insee = centre["com_insee"]
    rdv_site_web = centre["rdv_site_web"]
    logger.info(f"Vaccine Center {vaccine_center}: looking for an appointment")
    request = ScraperRequest(rdv_site_web, today)
    date = mapharma_fetch_slots(request)
    centres_scannes += 1
    if not date:
        logger.info(f"Vaccine Center {com_insee} {vaccine_center}: no appointment found")
        return
    logger.info(f"Vaccine Center {com_insee} {vaccine_center}: next appointment found: {date}")
    centres_trouves += 1


def main():
    centres = mapharma_centre_iterator()
    for centre in centres:
        mapharma_scrape(centre)
    logger.info(f'{centres_scannes} centres scannés, {centres_trouves} avec des dispos')


if __name__ == "__main__":
    main()
