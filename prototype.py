import os
import io
import re
import csv
import requests


DOCTOLIB_HEADERS = {
    'X-Covid-Tracker-Key': os.environ.get('DOCTOLIB_API_KEY', None)
}


def fetch_doctolib_slots(rdv_site_web, start_date):
    centre = re.search(r'\/([^`\/]*)\?', rdv_site_web)
    if not centre:
        return None

    centre_api_url = f'https://partners.doctolib.fr/booking/{centre.group(1)}.json'
    response = requests.get(centre_api_url, headers=DOCTOLIB_HEADERS)
    response.raise_for_status()
    data = response.json()

    # visit_motive_categories
    # example: https://partners.doctolib.fr/hopital-public/tarbes/centre-de-vaccination-tarbes-ayguerote?speciality_id=5494&enable_cookies_consent=1
    visit_category = None
    for category in  data.get('data', {}).get('visit_motive_categories', []):
        if category['name'] == 'Non professionnels de santé':
            visit_category = category['id']
            break

    # visit_motive_id
    visit_motive_id = None
    for visit_motive in data.get('data', {}).get('visit_motives', []):
        if visit_motive['name'].startswith('1ère injection vaccin COVID-19') \
           and visit_motive.get('visit_motive_category_id') == visit_category:
            visit_motive_id = visit_motive['id']
            break

    if visit_motive_id is None:
        return None

    # practice_ids / agenda_ids
    agenda_ids = []
    practice_ids = []
    for agenda in data['data']['agendas']:
        if agenda['booking_disabled']:
            continue
        agenda_id = str(agenda['id'])
        for pratice_id, visit_motive_list in agenda['visit_motive_ids_by_practice_id'].items():
            if visit_motive_id in visit_motive_list:
                practice_ids.append(str(pratice_id))
                if agenda_id not in agenda_ids:
                    agenda_ids.append(agenda_id)

    if not agenda_ids or not practice_ids:
        return None


    # temporary_booking_disabled ??
    agenda_ids = '-'.join(agenda_ids)
    practice_ids = '-'.join(practice_ids)

    slots_api_url = f'https://partners.doctolib.fr/availabilities.json?start_date={start_date}&visit_motive_ids={visit_motive_id}&agenda_ids={agenda_ids}&insurance_sector=public&practice_ids={practice_ids}&destroy_temporary=true&limit=7'

    response = requests.get(slots_api_url, headers=DOCTOLIB_HEADERS)
    response.raise_for_status()

    slots = response.json()
    for slot in slots['availabilities']:
        if len(slot['slots']) > 0:
            return slot['slots'][0]['start_date']

    return None


def fetch_centre_slots(rdv_site_web, start_date):
    if rdv_site_web.startswith('https://partners.doctolib.fr'):
        return 'Doctolib', fetch_doctolib_slots(rdv_site_web, start_date)
    if rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        return 'Keldoc', None
    if rdv_site_web.startswith('https://www.maiia.com'):
        return 'Maiia', None
    return 'Autre', None
    

def centre_iterator():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row


def fetch_all_slots(start_date):
    output = []
    for row in centre_iterator():
        try:
            plateforme, slots = fetch_centre_slots(row['rdv_site_web'], start_date)
        except requests.exceptions.RequestException as e:
            print(row['rdv_site_web'], e)
            slots = None
            plateforme = None

        print(plateforme, slots, row['rdv_site_web'])

        output.append({
            'nom': row['nom'],
            'url': row['rdv_site_web'],
            'plateforme': plateforme,
            'prochain_rdv': slots
        })
    return output
        

print(fetch_all_slots('2021-04-15'))
