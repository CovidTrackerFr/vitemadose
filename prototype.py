import io
import re
import csv
import requests


def fetch_doctolib_slots(rdv_site_web, start_date):
    centre = re.search(r'\/([^`\/]*)\?', rdv_site_web)
    if not centre:
        return None

    centre_api_url = f'https://partners.doctolib.fr/booking/{centre.group(1)}.json'
    response = requests.get(centre_api_url)
    response.raise_for_status()
    data = response.json()

    agenda_ids = '-'.join([str(agenda['id']) for agenda in data['data']['agendas']])
    if not agenda_ids:
        return None

    slots_api_url = f'https://partners.doctolib.fr/availabilities.json?start_date={start_date}&visit_motive_ids=2557226&agenda_ids={agenda_ids}&insurance_sector=public&practice_ids=165752&destroy_temporary=true&limit=7'

    response = requests.get(slots_api_url)
    response.raise_for_status()
    return response.json()


def fetch_centre_slots(rdv_site_web, start_date):
    if rdv_site_web.startswith('https://partners.doctolib.fr'):
        return fetch_doctolib_slots(rdv_site_web, start_date), 'Doctolib'
    if rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        return None, 'keldoc'
    if rdv_site_web.startswith('https://www.maiia.com'):
        return None, 'Maiia'
    return None
    

def center_iterator():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row   


def fetch_all_slots(start_date):
    output = []
    for row in center_iterator():
        try:
            row['slots'], row['plateforme'] = fetch_centre_slots(row['rdv_site_web'], start_date)
        except Exception as e:
            print(e)
            row['slots'] = None
            row['plateforme'] = None
        orow = [row['nom'], row['rdv_site_web'], ]
        print(row['plateforme'], row['slots'])

print(fetch_all_slots('2021-04-03'))