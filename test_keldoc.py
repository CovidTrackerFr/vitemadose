from datetime import datetime
from multiprocessing import Pool

from scraper.keldoc.keldoc import fetch_slots

CENTER_ID = 0

def async_keldoc_scrape(website):
    vaccine_center = website.split('/')[-1].split('?')[0]
    #print("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    date = fetch_slots(website, datetime.now().strftime('%Y-%m-%d'))
    if not date:
        print("Vaccine Center {0}: no appointment found".format(vaccine_center))
        return
    print("Vaccine Center {0}: next appointment found: {1}".format(vaccine_center, date))


def main():
    with open('keldoc.txt', 'r') as file:
        content = file.read()
        websites = content.split('\n')
        pool = Pool(len(websites))
        pool.map(async_keldoc_scrape, websites)


if __name__ == "__main__":
    main()
