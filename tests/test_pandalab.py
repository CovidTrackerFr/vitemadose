#import scraper

from datetime import datetime
from multiprocessing import Pool, freeze_support

from scraper.pandalab import fetch_slots as pandalab_fetch_slots
from scraper.pandalab import centre_iterator as pandalab_centre_iterator

today = datetime.now().strftime('%Y-%m-%d')

def async_pandalab_scrape(centre):
    vaccine_center = centre["nom"]
    com_insee = centre["com_insee"]
    website = centre["rdv_site_web"]
    print("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    date = pandalab_fetch_slots(website, today)
    if not date:
        print(f"Vaccine Center {com_insee} {vaccine_center}: no appointment found")
        return
    print(f"Vaccine Center {com_insee} {vaccine_center}: next appointment found: {date}")


def main():
    centres = pandalab_centre_iterator()
    pool = Pool(20)
    pool.map(async_pandalab_scrape, centres)


if __name__ == "__main__":
    freeze_support()
    main()
