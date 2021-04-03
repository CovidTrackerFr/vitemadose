from datetime import datetime

from scraper import maiia_fetch_slots


def centre_iterator():
    import csv
    import os
    print(os.getcwd())
    with open('data/input/centres-vaccination.csv', newline='\n') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            yield row


def fetch_centre_slots(rdv_site_web, start_date):
    if rdv_site_web.startswith('https://www.maiia.com'):
        tmp_date_str = maiia_fetch_slots(rdv_site_web)
        if tmp_date_str:
            print(f"prochaine date pour {row['nom']} est {tmp_date_str}, {row['rdv_site_web']}")
        else:
            print(f"pas de date pour {row['nom']} : {row['rdv_site_web']}")
        return 'Maiia', tmp_date_str
    return 'Autre', None



if __name__ == '__main__':
    start_date = datetime.now().isoformat()[:10]
    for row in centre_iterator():
        _, tmp_date_str = fetch_centre_slots(row['rdv_site_web'], start_date)