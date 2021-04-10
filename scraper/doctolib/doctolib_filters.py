import re

from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER

DOCTOLIB_APPOINTMENT_REASON = [
    '1ère injection',
    '1ere dose',
    '1 ère injection',
    '1 ere injection',
    '1er injection',
    '1ere injection',
    'vaccination'
]

DOCTOLIB_CATEGORY = [
    'vaccination',
    'non professionnels de santé',
    'patients', #  50 - 55 ans avec comoribidtés
]


def is_category_relevant(category):
    if not category:
        return False

    category = category.lower()
    category = re.sub(' +', ' ', category)
    for allowed_categories in DOCTOLIB_APPOINTMENT_REASON:
        if allowed_categories in category:
            return True
    return False


# Filter by relevant appointments
def is_appointment_relevant(appointment_name):
    if not appointment_name:
        return False

    appointment_name = appointment_name.lower()
    appointment_name = re.sub(' +', ' ', appointment_name)
    for allowed_appointments in DOCTOLIB_APPOINTMENT_REASON:
        if allowed_appointments in appointment_name:
            return True
    return False


# Parse practitioner type from Doctolib booking data.
def parse_practitioner_type(name, data):
    if 'pharmacie' in name.lower():
        return DRUG_STORE
    profile = data.get('profile', {})
    specialty = profile.get('speciality', {})
    if specialty:
        slug = specialty.get('slug', None)
        if slug and slug == 'medecin-generaliste':
            return GENERAL_PRACTITIONER
    return VACCINATION_CENTER
