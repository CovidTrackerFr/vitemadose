import sys
import datetime as dt
from multiprocessing import Pool
import json
import os
import io
import csv
import requests
import pytz

from .departements import to_departement_number, import_departements
from .doctolib import fetch_slots as doctolib_fetch_slots
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots

POOL_SIZE = int(os.getenv('POOL_SIZE', 20))


def main():
    with Pool(POOL_SIZE) as pool:
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator(),
            1
        )
        compte_centres, compte_centres_avec_dispo = export_data(centres_cherchés)
        print(
            f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")
        if compte_centres_avec_dispo == 0:
            print(
                "Aucune disponibilité n'a été trouvée sur tous les centres, c'est bizarre, alors c'est probablement une erreur")
            exit(code=1)

    export_stats(compte_centres, compte_centres_avec_dispo)


def cherche_prochain_rdv_dans_centre(centre):
    start_date = dt.datetime.now().isoformat()[:10]
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
        print(
            f"erreur lors du traitement de la ligne avec le gid {centre['gid']}, com_insee={centre['com_insee']}")
        departement = ''

    print(
        f'{centre.get("gid", "")!s:>8} {plateforme!s:16} {next_slot or ""!s:32} {departement!s:6}')

    return {
        'departement': departement,
        'nom': centre['nom'],
        'url': centre['rdv_site_web'],
        'plateforme': plateforme,
        'prochain_rdv': next_slot
    }


def sort_center(center):
    if not center:
        return '-'
    if not 'prochain_rdv' in center or not center['prochain_rdv']:
        return '-'
    return center['prochain_rdv']


def export_data(centres_cherchés, outpath_format='data/output/{}.json'):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    par_departement = {
        code: {
            'version': 1,
            'last_updated': dt.datetime.now(
                tz=pytz.timezone('Europe/Paris')).isoformat(),
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
                par_departement[code_departement]['centres_indisponibles'].append(
                    centre)
            else:
                compte_centres_avec_dispo += 1
                par_departement[code_departement]['centres_disponibles'].append(centre)
        else:
            print(
                f"WARNING: le centre {centre['nom']} ({code_departement}) n'a pas pu être rattaché à un département connu")

    for code_departement, disponibilités in par_departement.items():
        if 'centres_disponibles' in disponibilités:
            disponibilités['centres_disponibles'] = sorted(
                disponibilités['centres_disponibles'], key=sort_center)
        outpath = outpath_format.format(code_departement)
        print(f'writing result to {outpath} file')
        with open(outpath, "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    return compte_centres, compte_centres_avec_dispo


def fetch_centre_slots(rdv_site_web, start_date, fetch_map: dict = None):
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = {
            'Doctolib': doctolib_fetch_slots,
            'Keldoc': keldoc_fetch_slots,
            'Maiia': maiia_fetch_slots,
        }

    rdv_site_web = rdv_site_web.strip()

    # Determine platform based on visit URL.
    if rdv_site_web.startswith(
            'https://partners.doctolib.fr') or rdv_site_web.startswith(
            'https://www.doctolib.fr'):
        platform = 'Doctolib'
    elif rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        platform = 'Keldoc'
    elif rdv_site_web.startswith('https://www.maiia.com'):
        platform = 'Maiia'
    else:
        return 'Autre', None

    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]
    return platform, fetch_impl(rdv_site_web, start_date)


def centre_iterator():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row


def export_stats(compte_centre, compte_centres_avec_dispo):
    stats_data = {
        "nbre_total_centre": compte_centre,
        "nbre_total_centre_dispo": compte_centres_avec_dispo
    }
    with open("data/output/stats.json", "w") as stats_file:
        json.dump(stats_data, stats_file)


if __name__ == "__main__":
    main()
