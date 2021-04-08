import scraper
import logging

from datetime import datetime
from multiprocessing import Pool, freeze_support

from scraper.pandalab import fetch_slots as pandalab_fetch_slots
from scraper.pandalab import centre_iterator as pandalab_centre_iterator
from scraper.pattern.scraper_result import ScraperResult
from scraper.pattern.scraper_request import ScraperRequest

logger = logging.getLogger('scraper')
today = datetime.now().strftime('%Y-%m-%d')

def async_pandalab_scrape(centre):
    vaccine_center = centre["nom"]
    com_insee = centre["com_insee"]
    rdv_site_web = centre["rdv_site_web"]
    logger.info("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    request = ScraperRequest(rdv_site_web, today)
    date = pandalab_fetch_slots(request)
    if not date:
        logger.info(f"Vaccine Center {com_insee} {vaccine_center}: no appointment found")
        return
    logger.info(f"Vaccine Center {com_insee} {vaccine_center}: next appointment found: {date}")


def main():
    centres = pandalab_centre_iterator()
    pool = Pool(20)
    pool.map(async_pandalab_scrape, centres)


if __name__ == "__main__":
    freeze_support()
    main()
