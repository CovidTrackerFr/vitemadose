from datetime import datetime
from multiprocessing import Pool
import json
import os
import io
from itertools import islice
import re
import csv
import requests
import pandas as pd

session = requests.session()
if os.getenv('WITH_TOR', 'no') == 'yes':
  session.proxies = {'http':  'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}

POOL_SIZE = int(os.getenv('POOL_SIZE', 20))
DOCTOLIB_HEADERS = {
    'X-Covid-Tracker-Key': os.environ.get('DOCTOLIB_API_KEY', None)
}

def main():
    with Pool(POOL_SIZE) as pool:
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator(),
            1
        )
        export_data(centres_cherchés)

def cherche_prochain_rdv_dans_centre(centre):
    start_date = datetime.now().isoformat()[:10]
    try:
        plateforme, next_slot = fetch_centre_slots(centre['rdv_site_web'], start_date)
    except Exception as e:
        print(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}")
        print(e)
        next_slot = None
        plateforme = None

    print(plateforme, next_slot, numero_departement(centre))
    return {
        'departement': numero_departement(centre),
        'nom': centre['nom'],
        'url': centre['rdv_site_web'],
        'plateforme': plateforme,
        'prochain_rdv': next_slot
    }

def export_data(centres_cherchés):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    par_departement = {
        code: {
            'version': 1,
            'last_updated': datetime.now().isoformat(),
            'centres_disponibles': [],
            'centres_indisponibles': []
        }
        for code in import_departements()
    }
    for centre in centres_cherchés:
        compte_centres += 1
        code_departement = centre['departement']
        if code_departement in par_departement:
            if centre['prochain_rdv'] is None:
                par_departement[code_departement]['centres_indisponibles'].append(centre)
            else:
                compte_centres_avec_dispo += 1
                par_departement[code_departement]['centres_disponibles'].append(centre)
        else:
            print(f"WARNING: le centre {centre['nom']} ({code_departement}) n'a pas pu être rattaché à un département connu")

    for code_departement, disponibilités in par_departement.items():
        print(f'writing result to {code_departement}.json file')
        with open(f'data/output/{code_departement}.json', "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    print (f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")


def fetch_centre_slots(rdv_site_web, start_date):
    if rdv_site_web.startswith('https://partners.doctolib.fr'):
        return 'Doctolib', fetch_doctolib_slots(rdv_site_web, start_date)
    if rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        return 'Keldoc', None
    if rdv_site_web.startswith('https://www.maiia.com'):
        return 'Maiia', None
    return 'Autre', None


def fetch_doctolib_slots(rdv_site_web, start_date):
    centre = re.search(r'\/([^`\/]*)\?', rdv_site_web)
    if not centre:
        return None

    centre_api_url = f'https://partners.doctolib.fr/booking/{centre.group(1)}.json'
    response = session.get(centre_api_url, headers=DOCTOLIB_HEADERS)
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

    response = session.get(slots_api_url, headers=DOCTOLIB_HEADERS)
    response.raise_for_status()

    slots = response.json()
    for slot in slots['availabilities']:
        if len(slot['slots']) > 0:
            return slot['slots'][0]['start_date']

    return None


def centre_iterator():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = session.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row


# NOTE:
# les codes INSEE de communes sont _normalement_ sur 5 chiffres
#   - SAUF, si on a mis le type de la colonne à "nombre" dans excel et qu'il vire le 0 au début de 02401
# Le code INSEE commence par le code du département sur ses 2 premiers caractères
#   - SAUF pour l'outre-mer (>96) où c'est concrètement le bordel
#         
def numero_departement(centre):
    code_insee = centre['com_insee']
    if len(code_insee) == 4:
        code_insee = '0' + code_insee
    if code_insee.startswith('977') or code_insee.startswith('978'):
        return '971'
    if code_insee.startswith('97'):
        return code_insee[:3]
    return code_insee[:2]

def import_departements():
    import csv
    with open('data/input/departements-france.csv', newline='\n') as csvfile:
        reader = csv.DictReader(csvfile)
        return [str(row["code_departement"]) for row in reader]


main()
