import sys
import csv
import datetime as dt
import io
import json
import os
from multiprocessing import Pool

import pytz
import requests

from utils.vmd_logger import get_logger, enable_logger_for_production, enable_logger_for_debug
from .departements import to_departement_number, import_departements
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots

POOL_SIZE = int(os.getenv('POOL_SIZE', 20))
logger = get_logger()


def main():
    if len(sys.argv) == 1:
        scrape()
    else:
        scrape_debug(sys.argv[1:])


def get_start_date():
    return dt.date.today().isoformat()


def scrape_debug(urls):
    enable_logger_for_debug()
    start_date = get_start_date()
    for rdv_site_web in urls:
        logger.info('scraping URL %s', rdv_site_web)
        try:
            plateforme, next_slot = fetch_centre_slots(rdv_site_web, start_date)
        except Exception as e:
            logger.exception(f"erreur lors du traitement")
            next_slot = None
            plateforme = None
        logger.info(f'{plateforme!s:16} {next_slot or ""!s:32}')


def scrape():
    enable_logger_for_production()
    with Pool(POOL_SIZE) as pool:
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator(),
            1
        )
        compte_centres, compte_centres_avec_dispo = export_data(centres_cherchés)
        logger.info(f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")
        if compte_centres_avec_dispo == 0:
            logger.error("Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur")
            exit(code=1)


def cherche_prochain_rdv_dans_centre(centre):
    start_date = get_start_date()
    try:
        plateforme, next_slot = fetch_centre_slots(centre['rdv_site_web'], start_date)
    except Exception as e:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']} {str(e)}")
        next_slot = None
        plateforme = None

    try:
        departement = to_departement_number(insee_code=centre['com_insee'])
    except ValueError:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}, com_insee={centre['com_insee']}")
        departement = ''

    logger.info(f'{centre.get("gid", "")!s:>8} {plateforme!s:16} {next_slot or ""!s:32} {departement!s:6}')

    if plateforme == 'Doctolib' and not centre['rdv_site_web'].islower():
        logger.info(f"Centre {centre['rdv_site_web']} URL contained an uppercase - lowering the URL")
        centre['rdv_site_web'] = centre['rdv_site_web'].lower()

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
            'last_updated': dt.datetime.now(tz=pytz.timezone('Europe/Paris')).isoformat(),
            'centres_disponibles': [],
            'centres_indisponibles': []
        }
        for code in import_departements()
    }
    
    for centre in centres_cherchés:
        centre['nom'] = centre['nom'].strip()
        compte_centres += 1
        code_departement = centre['departement']
        if code_departement in par_departement:
            if centre['prochain_rdv'] is None:
                par_departement[code_departement]['centres_indisponibles'].append(centre)
            else:
                compte_centres_avec_dispo += 1
                par_departement[code_departement]['centres_disponibles'].append(centre)
        else:
            logger.warning(f"le centre {centre['nom']} ({code_departement}) n'a pas pu être rattaché à un département connu")

    outpath = outpath_format.format("info_centres")
    with open(outpath, "w") as info_centres:
        json.dump(par_departement, info_centres, indent=2)

    for code_departement, disponibilités in par_departement.items():
        if 'centres_disponibles' in disponibilités:
            disponibilités['centres_disponibles'] = sorted(disponibilités['centres_disponibles'], key=sort_center)
        outpath = outpath_format.format(code_departement)
        logger.debug(f'writing result to {outpath} file')
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
            'Ordoclic': ordoclic_fetch_slots,
        }

    rdv_site_web = rdv_site_web.strip()

    # Determine platform based on visit URL.
    if rdv_site_web.startswith('https://partners.doctolib.fr') or rdv_site_web.startswith('https://www.doctolib.fr'):
        platform = 'Doctolib'
    elif rdv_site_web.startswith('https://vaccination-covid.keldoc.com'):
        platform = 'Keldoc'
    elif rdv_site_web.startswith('https://www.maiia.com'):
        platform = 'Maiia'
    elif rdv_site_web.startswith('https://app.ordoclic.fr/'):
        platform = 'Ordoclic'
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
    for centre in ordoclic_centre_iterator():
        yield centre


if __name__ == "__main__":
    main()
