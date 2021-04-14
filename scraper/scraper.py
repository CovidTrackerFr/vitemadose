import sys
import csv
import datetime as dt
import io
import json
import os
import traceback
from collections import deque
from multiprocessing import Pool
from typing import Counter
from scraper.profiler import Profiling, ProfiledPool

from scraper.error import ScrapeError, BlockedByDoctolibError

import pytz
import requests

from scraper.pattern.center_info import convert_csv_data_to_center_info, CenterInfo
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, VACCINATION_CENTER
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from utils.vmd_utils import departementUtils, fix_scrap_urls, is_reserved_center
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .doctolib.doctolib import center_iterator as doctolib_center_iterator
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia import fetch_slots as maiia_fetch_slots
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots
from .mapharma.mapharma import centre_iterator as mapharma_centre_iterator
from .mapharma.mapharma import fetch_slots as mapharma_fetch_slots
from random import random

POOL_SIZE = int(os.getenv('POOL_SIZE', 50))
PARTIAL_SCRAPE = float(os.getenv('PARTIAL_SCRAPE', 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))

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
        rdv_site_web = fix_scrap_urls(rdv_site_web)
        logger.info('scraping URL %s', rdv_site_web)
        try:
            result = fetch_centre_slots(rdv_site_web, start_date)
        except Exception as e:
            logger.exception(f"erreur lors du traitement")
        logger.info(
            f'{result.platform!s:16} {result.next_availability or ""!s:32}')


def scrape() -> None:
    compte_centres = 0
    compte_centres_avec_dispo = 0
    compte_bloqués = 0
    profiled_pool = ProfiledPool(POOL_SIZE)
    with profiled_pool as pool:
        centre_iterator_proportion = (
            c for c in centre_iterator() if random() < PARTIAL_SCRAPE)
        centres_cherchés = pool.imap_unordered(
            cherche_prochain_rdv_dans_centre,
            centre_iterator_proportion,
            1
        )
        compte_centres, compte_centres_avec_dispo, compte_bloqués = export_data(
            centres_cherchés)

    logger.info(
        f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés")
    profiled_pool.profiler.print_summary()
    if compte_centres_avec_dispo == 0:
        logger.error(
            "Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur")
        exit(code=1)

    if compte_bloqués > 10:
        logger.error(
            "Notre IP a été bloquée par le CDN Doctolib plus de 10 fois. Pour éviter de pousser des données erronées, on s'arrête ici")
        exit(code=2)


def cherche_prochain_rdv_dans_centre(centre: dict) -> CenterInfo:
    center_data = convert_csv_data_to_center_info(centre)
    start_date = get_start_date()
    has_error = None
    result = None
    try:
        result = fetch_centre_slots(centre['rdv_site_web'], start_date)
        center_data.fill_result(result)
    except ScrapeError as scrape_error:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {centre['gid']} {str(scrape_error)}")
        has_error = scrape_error
    except Exception as e:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {centre['gid']}")
        traceback.print_exc()

    if has_error is None:
        logger.info(
            f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {center_data.prochain_rdv or ""!s:32} {center_data.departement!s:6}')
    else:
        logger.info(
            f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {"Erreur" or ""!s:32} {center_data.departement!s:6}')

    if result is not None and result.request.url is not None:
        center_data.url = result.request.url.lower()

    if 'type' in centre:
        center_data.type = centre['type']
    if not center_data.type:
        center_data.type = VACCINATION_CENTER
    center_data.gid = centre.get("gid", "")
    logger.debug(center_data.default())
    return center_data


def sort_center(center: dict) -> str:
    if not center:
        return '-'
    return center.get('prochain_rdv', '-')


def export_data(centres_cherchés, outpath_format='data/output/{}.json'):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    bloqués_doctolib = 0
    centres_open_data = []
    par_departement = {
        code: {
            'version': 1,
            'last_updated': dt.datetime.now(tz=pytz.timezone('Europe/Paris')).isoformat(),
            'centres_disponibles': [],
            'centres_indisponibles': []
        }
        for code in departementUtils.import_departements()
    }

    # This should be duplicate free, they are already checked in
    for centre in centres_cherchés:
        centre.nom = centre.nom.strip()

        if is_reserved_center(centre):
            continue
        compte_centres += 1
        code_departement = centre.departement

        if code_departement not in par_departement:
            logger.warning(
                f"le centre {centre.nom} ({code_departement}) n'a pas pu être rattaché à un département connu")
            continue
        erreur = centre.erreur
        centres_open_data.append(copy_omit_keys(centre.default(), ['prochain_rdv', 'internal_id', 'metadata',
                                                                   'location', 'appointment_count', 'erreur',
                                                                   'ville', 'type', 'vaccine_type']))
        if centre.prochain_rdv is None or centre.appointment_count == 0:
            par_departement[code_departement]['centres_indisponibles'].append(
                centre.default())
            if isinstance(erreur, BlockedByDoctolibError):
                par_departement[code_departement]['doctolib_bloqué'] = True
                bloqués_doctolib += 1
        else:
            compte_centres_avec_dispo += 1
            par_departement[code_departement]['centres_disponibles'].append(
                centre.default())

    outpath = outpath_format.format("info_centres")
    with open(outpath, "w") as info_centres:
        json.dump(par_departement, info_centres, indent=2)

    outpath = outpath_format.format("centres_open_data")
    with open(outpath, 'w') as centres_file:
        json.dump(centres_open_data, centres_file, indent=2)

    for code_departement, disponibilités in par_departement.items():
        disponibilités['last_updated'] = dt.datetime.now(
            tz=pytz.timezone('Europe/Paris')).isoformat()
        if 'centres_disponibles' in disponibilités:
            disponibilités['centres_disponibles'] = sorted(
                deduplicates_names(disponibilités['centres_disponibles']), key=sort_center)
        disponibilités["centres_indisponibles"] = deduplicates_names(
            disponibilités['centres_indisponibles'])
        outpath = outpath_format.format(code_departement)
        logger.debug(f'writing result to {outpath} file')
        with open(outpath, "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    return compte_centres, compte_centres_avec_dispo, bloqués_doctolib


@Profiling.measure('Any_slot')
def fetch_centre_slots(rdv_site_web, start_date, fetch_map: dict = None):
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = {
            'Doctolib': {'urls': [
                'https://partners.doctolib.fr',
                'https://www.doctolib.fr'
            ], 'scraper_ptr': doctolib_fetch_slots},
            'Keldoc': {'urls': [
                'https://vaccination-covid.keldoc.com',
                'https://keldoc.com'
            ], 'scraper_ptr': keldoc_fetch_slots},
            'Maiia': {'urls': [
                'https://www.maiia.com'
            ], 'scraper_ptr': maiia_fetch_slots},
            'Mapharma': {'urls': [
                'https://mapharma.net/',
            ], 'scraper_ptr': mapharma_fetch_slots},
            'Ordoclic': {'urls': [
                'https://app.ordoclic.fr/',
            ], 'scraper_ptr': ordoclic_fetch_slots}
        }

    rdv_site_web = fix_scrap_urls(rdv_site_web)
    request = ScraperRequest(rdv_site_web, start_date)

    # Determine platform based on visit URL
    platform = None
    for scraper_name in fetch_map:
        scraper = fetch_map[scraper_name]
        scrap = sum([1 if rdv_site_web.startswith(url)
                    else 0 for url in scraper.get('urls', [])])
        if scrap == 0:
            continue
        platform = scraper_name

    if not platform:
        return ScraperResult(request, 'Autre', None)
    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]['scraper_ptr']
    result = ScraperResult(request, platform, None)
    result.next_availability = fetch_impl(request)
    return result


def centre_iterator():
    visited_centers_links = set()
    for center in ialternate(ordoclic_centre_iterator(), mapharma_centre_iterator(),
                             doctolib_center_iterator(), gouv_centre_iterator()):
        if center["rdv_site_web"] not in visited_centers_links:
            visited_centers_links.add(center["rdv_site_web"])
            yield center


def gouv_centre_iterator(outpath_format='data/output/{}.json'):
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')

    total = 0

    centres_non_pris_en_compte = {
        "centres_fermes": {}, "centres_urls_vides": []}

    for row in csvreader:

        row["rdv_site_web"] = fix_scrap_urls(row["rdv_site_web"])
        if row["centre_fermeture"] == "t":
            centres_non_pris_en_compte["centres_fermes"][row["gid"]
                                                         ] = row["rdv_site_web"]

        if len(row["rdv_site_web"]):
            yield row
        else:
            centres_non_pris_en_compte["centres_urls_vides"].append(row["gid"])

        total += 1

    nb_fermes = len(centres_non_pris_en_compte["centres_fermes"])
    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])

    logger.info(
        f"Il y a {nb_fermes} centres fermes dans le fichier gouv sur un total de {total}")

    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])
    logger.info(
        f"Il y a {nb_urls_vides} centres avec une URL vide dans le fichier gouv sur un total de {total}")

    outpath = outpath_format.format("centres_non_pris_en_compte_gouv")
    with open(outpath, "w") as fichier:
        json.dump(centres_non_pris_en_compte, fichier, indent=2)


def copy_omit_keys(d, omit_keys):
    return {k: d[k] for k in set(list(d.keys())) - set(omit_keys)}


def ialternate(*iterators):
    queue = deque(iterators)
    while len(queue) > 0:
        iterator = queue.popleft()
        try:
            yield next(iterator)
            queue.append(iterator)
        except StopIteration:
            pass


def deduplicates_names(departement_centers):
    """
    Removes unique names by appending city name
    in par_departement

    see https://github.com/CovidTrackerFr/vitemadose/issues/173
    """
    deduplicated_centers = []
    departement_center_names_count = Counter([center["nom"]
                                              for center in departement_centers])
    names_to_remove = {departement for departement in departement_center_names_count
                       if departement_center_names_count[departement] > 1}

    for center in departement_centers:
        if center["nom"] in names_to_remove:
            center["nom"] = f"{center['nom']} - {departementUtils.get_city(center['metadata']['address'])}"
        deduplicated_centers.append(center)
    return deduplicated_centers


if __name__ == "__main__":
    main()
