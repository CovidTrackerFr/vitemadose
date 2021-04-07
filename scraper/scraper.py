import sys
import csv
import datetime as dt
import io
import json
import os
from multiprocessing import Pool
from scraper.error import ScrapeError, BlockedByDoctolibError

import pytz
import requests

from scraper.pattern.center_info import convert_csv_data_to_center_info
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from .departements import to_departement_number, import_departements
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots

POOL_SIZE = int(os.getenv('POOL_SIZE', 20))

logger = enable_logger_for_production()

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
            result = fetch_centre_slots(rdv_site_web, start_date)
        except Exception as e:
            logger.exception(f"erreur lors du traitement")
        logger.info(f'{result.platform!s:16} {result.next_availability or ""!s:32}')


def scrape():
    with Pool(POOL_SIZE) as pool:
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator(),
            1
        )
        compte_centres, compte_centres_avec_dispo, compte_bloqués = export_data(centres_cherchés)
        logger.info(f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")
        if compte_centres_avec_dispo == 0:
            logger.error("Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur")
            exit(code=1)

        if compte_bloqués > 10:
            logger.error("Notre IP a été bloquée par le CDN Doctolib plus de 10 fois. Pour éviter de pousser des données erronées, on s'arrête ici")
            exit(code=2)



def cherche_prochain_rdv_dans_centre(centre):
    center_data = convert_csv_data_to_center_info(centre)
    start_date = get_start_date()
    has_error = None
    result = None
    try:
        result = fetch_centre_slots(centre['rdv_site_web'], start_date)
        center_data.fill_result(result)
    except ScrapeError as scrape_error:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']} {str(scrape_error)}")
        has_error = scrape_error
    except Exception as e:
        print(e)

    if has_error is None:
        logger.info(f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {center_data.prochain_rdv or ""!s:32} {center_data.departement!s:6}')
    else:
        logger.info(f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {"Erreur" or ""!s:32} {center_data.departement!s:6}')

    if result and result.platform == 'Doctolib' and not center_data.url.islower():
        logger.info(f"Centre {centre['rdv_site_web']} URL contained an uppercase - lowering the URL")
        center_data.url = center_data.url.lower()

    return center_data.default()

def sort_center(center):
    if not center:
        return '-'
    if not 'prochain_rdv' in center or not center['prochain_rdv']:
        return '-'
    return center['prochain_rdv']


def export_data(centres_cherchés, outpath_format='data/output/{}.json'):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    bloqués_doctolib = 0
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
            erreur = centre.pop('erreur', None)
            if centre['prochain_rdv'] is None:
                par_departement[code_departement]['centres_indisponibles'].append(centre)
                if isinstance(erreur, BlockedByDoctolibError):
                    par_departement[code_departement]['doctolib_bloqué'] = True
                    bloqués_doctolib += 1
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

    return compte_centres, compte_centres_avec_dispo, bloqués_doctolib


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
    request = ScraperRequest(rdv_site_web, start_date)

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
        return ScraperResult(request, 'Autre', None)

    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]
    result = ScraperResult(request, platform, None)
    result.next_availability = fetch_impl(request)
    return result


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
