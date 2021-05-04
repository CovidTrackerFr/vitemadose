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


def is_vaccination_center(center_dict):
    """ Determine if a center provide COVID19 vaccinations.
        See: https://github.com/CovidTrackerFr/vitemadose/issues/271

        Parameters
        ----------
        center_dict : "Center" dict
            Center dict, output by the doctolib_center_scrap.center_from_doctor_dict

        Returns
        ----------
        bool
            True if if we think the center provide COVID19 vaccination

        Example
        ----------
        >>> center_without_vaccination = {'gid': 'd258630', 'visit_motives': ['Dépistage COVID-19 test antigénique (prélèvement naso-pharyngé)', 'Dépistage COVID-19 test par ponction capillaire (goutte de sang)']}
        >>> is_vaccination_center(center_without_vaccination)
        False
        >>> center_with_vaccination = {'gid': 'd257554', 'visit_motives': ['1re injection vaccin COVID-19 (Pfizer-BioNTech)', '2de injection vaccin COVID-19 (Pfizer-BioNTech)', '1re injection vaccin COVID-19 (Moderna)', '2de injection vaccin COVID-19 (Moderna)']}
        >>> is_vaccination_center(center_with_vaccination)
        True
    """

    motives = center_dict.get('visit_motives', [])

    # We don't have any motiv
    # so this criteria isn't relevant to determine if a center is a vaccination center
    # considering it as a vaccination one to prevent mass filtering
    # see https://github.com/CovidTrackerFr/vitemadose/issues/271
    if len(motives) == 0:
        return True

    for motive in motives:
        if is_appointment_relevant(motive): # first vaccine motive, it's a vaccination center
            return True
    
    return False # No vaccination motives found