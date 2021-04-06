import re
from datetime import datetime

from httpx import TimeoutException

from scraper.keldoc.keldoc_routes import API_KELDOC_MOTIVES

KELDOC_COVID_SPECIALTIES = [
    'Maladies infectieuses'
]

KELDOC_APPOINTMENT_REASON = [
    '1ère inj',
    '1 ère inj',
    '1 ere inj',
    '1ere inj',
    '1ère dose',
    '1ere dose',
    '1 er inj',
    'inj 1',
    'inj. 1',
    'première injection',
    'covid19 - vaccination',
    'inj1'
]

KELDOC_COVID_SKILLS = [
    'Centre de vaccination COVID-19'
]


# Filter by relevant appointments
def is_appointment_relevant(appointment_name):
    if not appointment_name:
        return False

    appointment_name = appointment_name.lower()
    appointment_name = re.sub(' +', ' ', appointment_name)
    for allowed_appointments in KELDOC_APPOINTMENT_REASON:
        if allowed_appointments in appointment_name:
            return True
    return False


# Filter by relevant specialties
def is_specialty_relevant(specialty):
    if not specialty:
        return False

    id = specialty.get('id', None)
    name = specialty.get('name', None)
    skills = specialty.get('skills', {})
    if not id or not name:
        return False
    for skill in skills:
        skill_name = skill.get('name', None)
        if not skill_name:
            continue
        if skill_name in KELDOC_COVID_SKILLS:
            return True
    for allowed_specialties in KELDOC_COVID_SPECIALTIES:
        if allowed_specialties == name:
            return True
    return False


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


def filter_vaccine_specialties(specialties):
    if not specialties:
        return False
    # Put relevant specialty & cabinet IDs in lists
    vaccine_specialties = []
    for specialty in specialties:
        if not is_specialty_relevant(specialty):
            continue
        vaccine_specialties.append(specialty.get('id', None))
    return vaccine_specialties


def filter_vaccine_motives(session, selected_cabinet, id, vaccine_specialties, vaccine_cabinets):
    if not id or not vaccine_specialties or not vaccine_cabinets:
        return None

    motive_categories = []
    vaccine_motives = []

    for specialty in vaccine_specialties:
        for cabinet in vaccine_cabinets:
            if selected_cabinet is not None and cabinet != selected_cabinet:
                continue
            try:
                motive_req = session.get(API_KELDOC_MOTIVES.format(id, specialty, cabinet))
            except TimeoutException:
                continue
            motive_req.raise_for_status()
            motive_data = motive_req.json()
            motive_categories.extend(motive_data)

    for motive_cat in motive_categories:
        motives = motive_cat.get('motives', {})
        for motive in motives:
            motive_name = motive.get('name', None)
            if not motive_name or not is_appointment_relevant(motive_name):
                continue
            motive_agendas = [motive_agenda.get('id', None) for motive_agenda in motive.get('agendas', {})]
            vaccine_motives.append({
                'id': motive.get('id', None),
                'agendas': motive_agendas
            })
    return vaccine_motives
