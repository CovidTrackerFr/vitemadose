from datetime import datetime
from multiprocessing import Pool

from scraper.ordoclic import centre_iterator as ordoclic_centre_iterator
from scraper.ordoclic import fetch_slots as ordoclic_fetch_slots
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult

today = datetime.now().strftime('%Y-%m-%d')

def async_ordoclic_scrape(centre):
    vaccine_center = centre["nom"]
    website = centre["rdv_site_web"]
    #print("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    request = ScraperRequest(website, today)
    date = ordoclic_fetch_slots(request)
    if not date:
        print(f"Vaccine Center {vaccine_center}: no appointment found")
        return
    print(f"Vaccine Center {vaccine_center}: next appointment found: {date}")


def main():
    centres = ordoclic_centre_iterator()
    pool = Pool(20)
    pool.map(async_ordoclic_scrape, centres)


if __name__ == "__main__":
    main()
