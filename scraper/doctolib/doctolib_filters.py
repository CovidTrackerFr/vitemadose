import re

from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER

DOCTOLIB_APPOINTMENT_REASON = [
    '1 ere injection',
    '1 ère injection',
    '1er injection',
    '1ere dose',
    '1ere injection',
    '1ère injection',
    '1re injection',
    'vaccination',
    'Vaccin COVID-19',
]
DOCTOLIB_APPOINTMENT_REASON = [c.lower().strip() for c in DOCTOLIB_APPOINTMENT_REASON]

DOCTOLIB_CATEGORY = [
    '70 ans',
    'astra Zeneca',
    'je ne suis pas professionnel de santé',
    'je suis un particulier',
    'non professionnels de santé',
    'patient',
    'personnes à très haut risque',
    'personnes âgées de 60 ans ou plus',
    'personnes de 60 ans et plus',
    'personnes de plus de',
    'pfizer',
    'public',
    'vaccination au centre',
    'vaccination covid',  # 50 - 55 ans avec comoribidtés
    'vaccination pfizer',
]
DOCTOLIB_CATEGORY = [c.lower().strip() for c in DOCTOLIB_CATEGORY]


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
    """ Tell if an appointment name is related to COVID-19 vaccination

        Example
        ----------
        >>> is_appointment_relevant("Vaccin COVID-19 - AstraZeneca (55 ans et plus)")
        True
        >>> is_appointment_relevant("Injection unique vaccin COVID-19 (Janssen)")
        True
        >>> is_appointment_relevant("consultation pré-vaccinale Pfizer-Moderna")
        False
    """
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
