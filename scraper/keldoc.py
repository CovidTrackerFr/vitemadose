from datetime import datetime, timedelta
from urllib.parse import urlsplit, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

session = requests.Session()

retries = Retry(total=2,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

KELDOC_COVID_SPECIALTIES = [
    'Maladies infectieuses'
]

KELDOC_APPOINTMENT_REASON = [
    '1ère injection'
]


# Filter by relevant appointments
def is_appointment_relevant(appointment_name):
    if not appointment_name:
        return False

    appointment_name = appointment_name.lower()
    for allowed_appointments in KELDOC_APPOINTMENT_REASON:
        if allowed_appointments in appointment_name:
            return True
    return False


# Filter by revelant specialties
def is_specialty_relevant(specialty_name):
    if not specialty_name:
        return False

    for allowed_specialties in KELDOC_COVID_SPECIALTIES:
        if allowed_specialties == specialty_name:
            return True
    return False


# Get relevant cabinets
def get_relevant_cabinets(center_id, specialty_ids):
    cabinets = []
    if not center_id or not specialty_ids:
        return cabinets

    for specialty in specialty_ids:
        cabinet_url = f'https://booking.keldoc.com/api/patients/v2/clinics/{center_id}/specialties/{specialty}/cabinets'
        try:
            cabinet_req = session.get(cabinet_url, timeout=5)
        except requests.exceptions.Timeout:
            continue
        cabinet_req.raise_for_status()
        data = cabinet_req.json()
        if not data:
            return cabinets
        for cabinet in data:
            cabinet_id = cabinet.get('id', None)
            if not cabinet_id:
                continue
            cabinets.append(cabinet_id)
    return cabinets


def fetch_keldoc_motives(base_url, center_id, specialty_ids, cabinet_ids):
    if center_id is None or specialty_ids is None or cabinet_ids is None:
        return None

    motive_url = 'https://booking.keldoc.com/api/patients/v2/clinics/{0}/specialties/{1}/cabinets/{2}/motive_categories'
    motive_categories = []
    revelant_motives = []

    for specialty in specialty_ids:
        for cabinet in cabinet_ids:
            try:
                motive_req = session.get(motive_url.format(center_id, specialty, cabinet), timeout=10)
            except requests.exceptions.Timeout:
                continue
            motive_req.raise_for_status()
            motive_data = motive_req.json()
            for motive_cat in motive_data:
                motive_categories.append(motive_cat)

    for motive_cat in motive_categories:
        motives = motive_cat.get('motives', {})
        for motive in motives:
            motive_name = motive.get('name', None)

            if not motive_name or not is_appointment_relevant(motive_name):
                continue
            motive_agendas = [motive_agenda.get('id', None) for motive_agenda in motive.get('agendas', {})]
            motive_info = {
                'id': motive.get('id', None),
                'agendas': motive_agendas
            }
            revelant_motives.append(motive_info)
    return revelant_motives


def parse_keldoc_availability(availability_data):
    if not availability_data:
        return None
    if 'date' in availability_data:
        date = availability_data.get('date', None)
        date_obj = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%f%z')
        return date_obj

    availabilities = availability_data.get('availabilities', None)
    if availabilities is None:
        return None
    for date in availabilities:
        slots = availabilities.get(date, [])
        if not slots:
            continue
        for slot in slots:
            start_date = slot.get('start_time', None)
            if not start_date:
                continue
            return datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%S.%f%z')
    return None


def fetch_slots(rdv_site_web, start_date):
    # Fetch new URL after redirection
    try:
        rq = session.get(rdv_site_web, timeout=10)
    except requests.exceptions.Timeout:
        return None
    rq.raise_for_status()
    new_url = rq.url

    # Keldoc needs an end date, but if no appointment are found,
    # it still returns the next available appointment. Bigger end date
    # makes Keldoc responses slower.
    date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

    # Parse revelant GET params for Keldoc API requests
    query = urlsplit(new_url).query
    params_get = parse_qs(query)
    mandatory_params = ['dom', 'inst', 'user']
    # Some vaccination centers on Keldoc do not
    # accept online appointments, so you cannot retrieve a date
    for mandatory_param in mandatory_params:
        if not mandatory_param in params_get:
            return None
    resource_params = {
        'type': params_get.get('dom')[0],
        'location': params_get.get('inst')[0],
        'slug': params_get.get('user')[0]
    }

    # Fetch center id
    resource_url = f'https://booking.keldoc.com/api/patients/v2/searches/resource'
    try:
        resource = session.get(resource_url, params=resource_params, timeout=10)
    except requests.exceptions.Timeout:
        return None
    resource.raise_for_status()
    data = resource.json()

    center_id = data.get('id', None)
    if not center_id:
        return None

    # Put revelant specialty & cabinet IDs in lists
    specialty_ids = []
    for specialty in data.get('specialties', {}):
        if not is_specialty_relevant(specialty.get('name', None)):
            continue
        specialty_ids.append(specialty.get('id', None))
    cabinet_ids = get_relevant_cabinets(center_id, specialty_ids)
    revelant_motives = fetch_keldoc_motives(rdv_site_web, center_id, specialty_ids, cabinet_ids)
    if revelant_motives is None:
        return None

    # Find next availabilities
    first_availability = None
    for revelant_motive in revelant_motives:
        if not 'id' in revelant_motive or not 'agendas' in revelant_motive:
            continue
        motive_id = revelant_motive.get('id', None)
        calendar_url = f'https://www.keldoc.com/api/patients/v2/timetables/{motive_id}'
        calendar_params = {
            'from': start_date,
            'to': end_date,
            'agenda_ids[]': revelant_motive.get('agendas', [])
        }
        try:
            calendar_req = session.get(calendar_url, params=calendar_params, timeout=10)
        except requests.exceptions.Timeout:
            # Some requests on Keldoc are taking too much time (for few centers)
            # and block the process completion.
            continue
        calendar_req.raise_for_status()

        date = parse_keldoc_availability(calendar_req.json())
        if date is None:
            continue
        # Compare first available date
        if first_availability is None or date < first_availability:
            first_availability = date
    if not first_availability:
        return None
    return first_availability.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
