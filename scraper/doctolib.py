import os
import re
from typing import Optional, Tuple

import httpx
import requests

DOCTOLIB_HEADERS = {
    'X-Covid-Tracker-Key': os.environ.get('DOCTOLIB_API_KEY', ''),
}

DEFAULT_CLIENT: httpx.Client

if os.getenv('WITH_TOR', 'no') == 'yes':
    session = requests.Session()
    session.proxies = {  # type: ignore
        'http': 'socks5://127.0.0.1:9050',
        'https': 'socks5://127.0.0.1:9050',
    }
    DEFAULT_CLIENT = session  # type: ignore
else:
    DEFAULT_CLIENT = httpx.Client()


def fetch_slots(rdv_site_web, start_date):
    # Fonction principale avec le comportement "de prod".
    doctolib = DoctolibSlots(client=DEFAULT_CLIENT)
    return doctolib.fetch(rdv_site_web, start_date)


class DoctolibSlots:
    # Permet de passer un faux client HTTP,
    # pour éviter de vraiment appeler Doctolib lors des tests.

    def __init__(self, client: httpx.Client = None) -> None:
        self._client = DEFAULT_CLIENT if client is None else client

    def fetch(self, rdv_site_web: str, start_date: str) -> Optional[str]:
        centre = _parse_centre(rdv_site_web)

        centre_api_url = f'https://partners.doctolib.fr/booking/{centre}.json'
        response = self._client.get(centre_api_url, headers=DOCTOLIB_HEADERS)
        response.raise_for_status()
        data = response.json()

        # visit_motive_categories
        # example: https://partners.doctolib.fr/hopital-public/tarbes/centre-de-vaccination-tarbes-ayguerote?speciality_id=5494&enable_cookies_consent=1
        visit_category_id = _find_visit_motive_category_id(data)
        if visit_category_id is None:
            return None

        # visit_motive_id
        visit_motive_id = _find_visit_motive_id(data, visit_category_id)
        if visit_motive_id is None:
            return None

        # practice_ids / agenda_ids
        agenda_ids, practice_ids = _find_agenda_and_practice_ids(data, visit_motive_id)
        if not agenda_ids or not practice_ids:
            return None

        # temporary_booking_disabled ??

        agenda_ids_q = "-".join(agenda_ids)
        practice_ids_q = "-".join(practice_ids)
        slots_api_url = f'https://partners.doctolib.fr/availabilities.json?start_date={start_date}&visit_motive_ids={visit_motive_id}&agenda_ids={agenda_ids_q}&insurance_sector=public&practice_ids={practice_ids_q}&destroy_temporary=true&limit=7'

        response = self._client.get(slots_api_url, headers=DOCTOLIB_HEADERS)
        response.raise_for_status()

        slots = response.json()
        for slot in slots['availabilities']:
            if len(slot['slots']) > 0:
                return slot['slots'][0]['start_date']

        return slots.get('next_slot')


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


def _find_visit_motive_category_id(data: dict) -> Optional[str]:
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID de la catégorie de motif correspondant à 'Non professionnels de santé'
    (qui correspond à la population civile).
    """
    for category in data.get('data', {}).get('visit_motive_categories', []):
        if category['name'] == 'Non professionnels de santé':
            return category['id']
    return None


def _find_visit_motive_id(data: dict, visit_motive_category_id: str) -> Optional[str]:
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID du 1er motif de visite disponible correspondant à une 1ère dose pour
    la catégorie de motif attendue.
    """
    for visit_motive in data.get('data', {}).get('visit_motives', []):
        # On ne gère que les 1ère doses (le RDV pour la 2e dose est en général donné
        # après la 1ère dose, donc les gens n'ont pas besoin d'aide pour l'obtenir).
        if not visit_motive['name'].startswith('1ère injection vaccin COVID-19'):
            continue
        if visit_motive.get('visit_motive_category_id') == visit_motive_category_id:
            return visit_motive['id']
    return None


def _find_agenda_and_practice_ids(data: dict, visit_motive_id: str) -> Tuple[list, list]:
    """
    Etant donné une réponse à /booking/<centre>.json, renvoie tous les
    "agendas" et "pratiques" (jargon Doctolib) qui correspondent au motif de visite.
    On a besoin de ces valeurs pour récupérer les disponibilités.
    """
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
    return agenda_ids, practice_ids
