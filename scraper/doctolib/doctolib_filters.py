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
    'non professionnels de santé',
    'patient',
    'vaccination au centre',
    '70 ans',
    'je suis un particulier',
    'je ne suis pas professionnel de santé',
    'vaccination pfizer',
    'grand public',
    'personnes de plus de',
    'vaccination covid',  # 50 - 55 ans avec comoribidtés
]


def is_category_relevant(category):
    if not category:
        return False

    category = category.lower().strip()
    category = re.sub(' +', ' ', category)
    for allowed_categories in DOCTOLIB_CATEGORY:
        if allowed_categories in category:
            return True
    # Weird centers. But it's vaccination related COVID-19.
    if category == 'vaccination':
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