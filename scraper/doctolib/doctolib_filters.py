import re

from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER
from utils.vmd_config import get_conf_platform

DOCTOLIB_CONF = get_conf_platform("doctolib")
DOCTOLIB_FILTERS = DOCTOLIB_CONF.get("filters", {})

DOCTOLIB_APPOINTMENT_REASON = DOCTOLIB_FILTERS.get("appointment_reason", [])
DOCTOLIB_APPOINTMENT_REASON = [c.lower().strip() for c in DOCTOLIB_APPOINTMENT_REASON]

DOCTOLIB_CATEGORY = DOCTOLIB_FILTERS.get("appointment_category", [])
DOCTOLIB_CATEGORY = [c.lower().strip() for c in DOCTOLIB_CATEGORY]


def is_category_relevant(category):
    if not category:
        return False

    category = category.lower().strip()
    category = re.sub(" +", " ", category)
    for allowed_categories in DOCTOLIB_CATEGORY:
        if allowed_categories in category:
            return True
    # Weird centers. But it's vaccination related COVID-19.
    if category == "vaccination":
        return True
    return False


# Filter by relevant appointments
def is_appointment_relevant(motive_id):

    vaccination_motives = [int(item) for item in DOCTOLIB_FILTERS["motives"].keys()]
    """Tell if an appointment name is related to COVID-19 vaccination

    Example
    ----------
    >>> is_appointment_relevant(6970)
    True
    >>> is_appointment_relevant(245617)
    False
    """
    if not motive_id:
        return False

    if motive_id in vaccination_motives:
        return True

    return False


def dose_number(motive_id: int):
    if not motive_id:
        return None
    dose_number = DOCTOLIB_FILTERS["motives"][str(motive_id)]["dose"]
    if dose_number:
        return dose_number
    return None


# Parse practitioner type from Doctolib booking data.
def parse_practitioner_type(name, data):
    if "pharmacie" in name.lower():
        return DRUG_STORE
    profile = data.get("profile", {})
    specialty = profile.get("speciality", {})
    if specialty:
        slug = specialty.get("slug", None)
        if slug and slug == "medecin-generaliste":
            return GENERAL_PRACTITIONER
    return VACCINATION_CENTER


def is_vaccination_center(center_dict):
    """Determine if a center provide COVID19 vaccinations.
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
    >>> center_without_vaccination = {'gid': 'd258630', 'visit_motives_ids': [224512]}
    >>> is_vaccination_center(center_without_vaccination)
    False
    >>> center_with_vaccination = {'gid': 'd257554', 'visit_motives_ids': [6970]}
    >>> is_vaccination_center(center_with_vaccination)
    True
    """
    motives = center_dict.get("visit_motives_ids", [])

    # We don't have any motiv
    # so this criteria isn't relevant to determine if a center is a vaccination center
    # considering it as a vaccination one to prevent mass filtering
    # see https://github.com/CovidTrackerFr/vitemadose/issues/271
    if len(motives) == 0:
        return True

    for motive in motives:
        if is_appointment_relevant(motive):  # first vaccine motive, it's a vaccination center
            return True

    return False  # No vaccination motives found
