from datetime import datetime
from multiprocessing import Pool
import json
import os
import io
import csv
import requests

from .departements import to_departement_number, import_departements
from .doctolib import fetch_slots as doctolib_fetch_slots
from .keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots


POOL_SIZE = int(os.getenv('POOL_SIZE', 20))


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

    try:
        departement = to_departement_number(insee_code=centre['com_insee'])
    except ValueError:
        print(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}, com_insee={centre['com_insee']}")
        departement = ''

    print(f'{centre["gid"]:>8} {plateforme:16} {next_slot or ""!s:32} {departement:6}')

    return {
        'departement': departement,
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

    print(f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")


def fetch_centre_slots(rdv_site_web, start_date):
    rdv_site_web = rdv_site_web.strip()
    if rdv_site_web.startswith('https://partners.doctolib.fr') or rdv_site_web.startswith('https://www.doctolib.fr'):
        return 'Doctolib', doctolib_fetch_slots(rdv_site_web, start_date)
    if rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        return 'Keldoc', keldoc_fetch_slots(rdv_site_web, start_date)
    if rdv_site_web.startswith('https://www.maiia.com'):
        return 'Maiia', maiia_fetch_slots(rdv_site_web, start_date)
    return 'Autre', None


def centre_iterator():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row


if __name__ == "__main__":
    main()
