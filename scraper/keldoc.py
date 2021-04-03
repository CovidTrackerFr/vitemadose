from datetime import datetime, timedelta
from urllib.parse import urlsplit, parse_qs

import requests

session = requests.Session()


def fetch_keldoc_motives(center_id, specialty_ids, cabinet_ids):
    if center_id is None or specialty_ids is None or cabinet_ids is None:
        return None

    motive_url = 'https://booking.keldoc.com/api/patients/v2/clinics/{0}/specialties/{1}/cabinets/{2}/motive_categories'
    motive_categories = []
    revelant_motives = []

    for specialty in specialty_ids:
        for cabinet in cabinet_ids:
            motive_req = session.get(motive_url.format(center_id, specialty, cabinet))
            motive_data = motive_req.json()
            for motive_cat in motive_data:
                motive_categories.append(motive_cat)

    for motive_cat in motive_categories:
        motives = motive_cat.get('motives', {})
        for motive in motives:
            motive_name = motive.get('name', None)
            if not motive_name or not '1ère injection' in motive_name.lower():
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
    rq = session.get(rdv_site_web)
    new_url = rq.url

    # Keldoc needs an end date, but if no appointment are found,
    # it still returns the next available appointment. Bigger end date
    # makes Keldoc responses slower.
    date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = date_obj + timedelta(days=1)
    end_date = date_obj.strftime('%Y-%m-%d')

    # Parse revelant GET params for Keldoc API requests
    query = urlsplit(new_url).query
    params_get = parse_qs(query)
    resource_params = {
        'type': params_get.get('dom')[0],
        'location': params_get.get('inst')[0],
        'slug': params_get.get('user')[0]
    }

    # Fetch center id
    resource_url = f'https://booking.keldoc.com/api/patients/v2/searches/resource'
    resource = session.get(resource_url, params=resource_params)
    data = resource.json()

    center_id = data.get('id', None)
    if not center_id:
        return None

    # Put specialty & cabinet IDs in lists
    specialty_ids = [specialty.get('id', None) for specialty in data.get('specialties', {})]
    cabinet_ids = [cabinet.get('id', None) for cabinet in data.get('cabinets', {})]
    revelant_motives = fetch_keldoc_motives(center_id, specialty_ids, cabinet_ids)

    if revelant_motives is None:
        return None
    first_availability = None

    # Find next availabilities
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
        calendar_req = session.get(calendar_url, params=calendar_params)
        date = parse_keldoc_availability(calendar_req.json())
        if date is None:
            continue
        if first_availability is None or date < first_availability:
            first_availability = date
    if not first_availability:
        return None
    return first_availability.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
