import time
import logging
import os
import re
from datetime import date
from typing import Optional, Tuple

import httpx
import requests

from scraper.doctolib.doctolib_filters import is_appointment_relevant, get_etablissement_type, is_category_relevant
from scraper.pattern.scraper_request import ScraperRequest
from scraper.error import BlockedByDoctolibError

WAIT_SECONDS_AFTER_REQUEST = 0.100
DOCTOLIB_SLOT_LIMIT = 50

DOCTOLIB_HEADERS = {
    'User-Agent': os.environ.get('DOCTOLIB_API_KEY', ''),
}

DEFAULT_CLIENT: httpx.Client
logger = logging.getLogger('scraper')

if os.getenv('WITH_TOR', 'no') == 'yes':
    session = requests.Session()
    session.proxies = {  # type: ignore
        'http': 'socks5://127.0.0.1:9050',
        'https': 'socks5://127.0.0.1:9050',
    }
    DEFAULT_CLIENT = session  # type: ignore
else:
    DEFAULT_CLIENT = httpx.Client()


def fetch_slots(request: ScraperRequest):
    # Fonction principale avec le comportement "de prod".
    doctolib = DoctolibSlots(client=DEFAULT_CLIENT)
    return doctolib.fetch(request)


class DoctolibSlots:
    # Permet de passer un faux client HTTP,
    # pour éviter de vraiment appeler Doctolib lors des tests.

    def __init__(self, client: httpx.Client = None, cooldown_interval=WAIT_SECONDS_AFTER_REQUEST) -> None:
        self._cooldown_interval = cooldown_interval
        self._client = DEFAULT_CLIENT if client is None else client

    def fetch(self, request: ScraperRequest) -> Optional[str]:
        centre = _parse_centre(request.get_url())

        # Doctolib fetches multiple vaccination centers sometimes
        # so if a practice id is present in query, only related agendas
        # should be selected.
        practice_id = _parse_practice_id(request.get_url())

        centre_api_url = f'https://partners.doctolib.fr/booking/{centre}.json'
        response = self._client.get(centre_api_url, headers=DOCTOLIB_HEADERS)
        if response.status_code == 403:
            raise BlockedByDoctolibError(centre_api_url)

        response.raise_for_status()
        time.sleep(self._cooldown_interval)
        data = response.json()
        rdata = data.get('data', {})
        appointment_count = 0
        #request.update_practitioner_type(get_etablissement_type(centre, rdata))
        if practice_id:
            practice_id = link_practice_ids(practice_id, rdata)
        if len(rdata.get('places', [])) > 1 and practice_id is None:
            practice_id = rdata.get('places')[0].get('practice_ids', None)
        set_doctolib_center_internal_id(request, rdata, practice_id)
        # visit_motive_categories
        # example: https://partners.doctolib.fr/hopital-public/tarbes/centre-de-vaccination-tarbes-ayguerote?speciality_id=5494&enable_cookies_consent=1
        visit_motive_category_id = _find_visit_motive_category_id(data)
        # visit_motive_id
        visit_motive_ids = _find_visit_motive_id(data, visit_motive_category_id=visit_motive_category_id)

        if visit_motive_ids is None:
            return None
        # practice_ids / agenda_ids
        agenda_ids, practice_ids = _find_agenda_and_practice_ids(
            data, visit_motive_ids, practice_id_filter=practice_id
        )
        if not agenda_ids or not practice_ids:
            return None

        # temporary_booking_disabled ??

        agenda_ids_q = "-".join(agenda_ids)
        practice_ids_q = "-".join(practice_ids)
        start_date = request.get_start_date()

        first_availability = None
        for motive_id in visit_motive_ids:
            slots_api_url = f'https://partners.doctolib.fr/availabilities.json?start_date={start_date}&visit_motive_ids={motive_id}&agenda_ids={agenda_ids_q}&insurance_sector=public&practice_ids={practice_ids_q}&destroy_temporary=true&limit={DOCTOLIB_SLOT_LIMIT}'
            response = self._client.get(slots_api_url, headers=DOCTOLIB_HEADERS)
            if response.status_code == 403:
                raise BlockedByDoctolibError(centre_api_url)

            response.raise_for_status()
            time.sleep(self._cooldown_interval)

            slots = response.json()

            if slots.get('total'):
                appointment_count += int(slots.get('total', 0))
            for availability in slots['availabilities']:
                slot_list = availability.get('slots', None)
                if not slot_list or len(slot_list) == 0:
                    continue
                if isinstance(slot_list[0], str):
                    if not first_availability or slot_list[0] < first_availability:
                        first_availability = slot_list[0]
                for slot_info in slot_list:
                    sdate = slot_info.get('start_date', None)
                    if not sdate:
                        continue
                    if not first_availability or sdate < first_availability:
                        first_availability = sdate

            if type(slots) is dict:
                next_slot = slots.get('next_slot', None)
                if not next_slot:
                    continue
                if not first_availability or next_slot < first_availability:
                    first_availability = next_slot

        request.update_appointment_count(appointment_count)
        return first_availability


def set_doctolib_center_internal_id(request: ScraperRequest, data: dict, practice_ids):
    profile = data.get('profile')

    if not profile:
        return
    profile_id = profile.get('id', None)
    if not profile_id:
        return
    profile_id = int(profile_id)
    practices = "-".join(str(x) for x in practice_ids) if practice_ids is not None else ""
    request.internal_id = f"{profile_id}[{practices}]"


def _parse_centre(rdv_site_web: str) -> Optional[str]:
    """
    Etant donné l'URL de la page web correspondant au centre de vaccination,
    renvoie le nom du centre de vaccination, en lowercase.
    """
    match = re.search(r'\/([^`\/]+)\?', rdv_site_web)
    if match:
        # nouvelle URL https://partners.doctolib.fr/...
        return match.group(1)

    # ancienne URL https://www.doctolib.fr/....
    # centre doit être en minuscule
    centre = rdv_site_web.split('/')[-1].lower()
    if centre == '':
        return None
    return centre


def link_practice_ids(practice_id: list, rdata: dict):
    if not practice_id:
        return practice_id
    places = rdata.get('places')
    if not places:
        return practice_id
    base_place = None
    place_ids = []
    for place in places:
        place_id = place.get('id', None)
        if not place_id:
            continue
        place_ids.append(int(place_id.replace("practice-", "")))
        if place_id == f'practice-{practice_id[0]}':
            base_place = place
            break
    if not base_place:
        return place_ids
    for place in places:
        if place.get('id') == base_place.get('id'):
            continue
        if place.get('address') == base_place.get('address'):  # Tideous check
            practice_id.append(int(place.get('id').replace("practice-", "")))
    return practice_id


def _parse_practice_id(rdv_site_web: str):
    # Doctolib fetches multiple vaccination centers sometimes
    # so if a practice id is present in query, only related agendas
    # will be selected.
    params = httpx.QueryParams(httpx.URL(rdv_site_web).query)

    if 'pid' not in params:
        return None

    # QueryParams({'pid': 'practice-164984'}) -> 'practice-164984'
    # /!\ Some URL query strings look like this:
    # 1) ...?pid=practice-162589&?speciality_id=5494&enable_cookies_consent=1
    # 2) ...?pid=practice-162589?speciality_id=5494&enable_cookies_consent=1
    # Notice the weird &?speciality_id or ?speciality_id.
    # Case 1) is handled correctly by `httpx.QueryParams`: in that
    # case, 'pid' contains 'practice-164984'.
    # Case 2), 'pid' contains 'pid=practice-162589?speciality_id=5494'
    # which must be handled manually.
    pid = params.get('pid')
    if pid is None:
        return None

    try:
        # -> '164984'
        pid = pid.split('-')[-1]
        # May be '164984?specialty=13' due to a weird format, drop everything after '?'
        pid, _, _ = pid.partition('?')
        # -> 164984
        return [int(pid)]
    except (ValueError, TypeError, IndexError):
        logger.error(f'failed to parse practice ID: {pid=}')
        return None


def _find_visit_motive_category_id(data: dict):
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID de la catégorie de motif correspondant à 'Non professionnels de santé'
    (qui correspond à la population civile).
    """
    categories = []
    for category in data.get('data', {}).get('visit_motive_categories', []):
        if is_category_relevant(category['name']):
            categories.append(category['id'])
    return categories


def _find_visit_motive_id(data: dict, visit_motive_category_id: list = None):
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID du 1er motif de visite disponible correspondant à une 1ère dose pour
    la catégorie de motif attendue.
    """
    relevant_motives = []
    for visit_motive in data.get('data', {}).get('visit_motives', []):
        # On ne gère que les 1ère doses (le RDV pour la 2e dose est en général donné
        # après la 1ère dose, donc les gens n'ont pas besoin d'aide pour l'obtenir).
        if not is_appointment_relevant(visit_motive['name']):
            continue
        # If this motive isn't related to vaccination
        if not visit_motive.get('vaccination_motive'):
            continue
        # If it's not a first shot motive
        # TODO: filter system
        if not visit_motive.get('first_shot_motive'):
            continue
        # Si le lieu de vaccination n'accepte pas les nouveaux patients
        # on ne considère pas comme valable.
        if 'allow_new_patients' in visit_motive and not visit_motive['allow_new_patients']:
            continue
        # NOTE: 'visit_motive_category_id' agit comme un filtre. Il y a 2 cas :
        # * visit_motive_category_id=None : pas de filtre, et on veut les motifs qui ne
        # sont pas non plus rattachés à une catégorie
        # * visit_motive_category_id=<id> : filtre => on veut les motifs qui
        # correspondent à la catégorie en question.
        if visit_motive.get('visit_motive_category_id') in visit_motive_category_id or not visit_motive_category_id:
            relevant_motives.append(visit_motive['id'])
    return relevant_motives


def _find_agenda_and_practice_ids(data: dict, visit_motive_id: list, practice_id_filter: list = None) -> Tuple[
    list, list]:
    """
    Etant donné une réponse à /booking/<centre>.json, renvoie tous les
    "agendas" et "pratiques" (jargon Doctolib) qui correspondent au motif de visite.
    On a besoin de ces valeurs pour récupérer les disponibilités.
    """
    agenda_ids = set()
    practice_ids = set()
    for agenda in data['data']['agendas']:
        if (
                'practice_id' in agenda
                and practice_id_filter is not None
                and agenda['practice_id'] not in practice_id_filter
        ):
            continue
        if agenda['booking_disabled']:
            continue
        agenda_id = str(agenda['id'])
        for pratice_id, visit_motive_list in agenda['visit_motive_ids_by_practice_id'].items():
            for motive in visit_motive_id:
                if motive in visit_motive_list:
                    practice_ids.add(str(pratice_id))
                    agenda_ids.add(agenda_id)
    return sorted(agenda_ids), sorted(practice_ids)
