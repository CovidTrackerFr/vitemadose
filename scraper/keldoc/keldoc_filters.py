import re
from datetime import datetime

from httpx import TimeoutException

from scraper.keldoc.keldoc_routes import API_KELDOC_MOTIVES
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from utils.vmd_config import get_conf_platform

KELDOC_CONF = get_conf_platform("keldoc")
KELDOC_FILTERS = KELDOC_CONF.get("filters", {})

KELDOC_COVID_SPECIALTIES = KELDOC_FILTERS.get("appointment_speciality", [])

KELDOC_APPOINTMENT_REASON = KELDOC_FILTERS.get("appointment_reason", [])

KELDOC_COVID_SKILLS = KELDOC_FILTERS.get("appointment_skill", [])


def parse_keldoc_availability(availability_data, appointments):
    if not availability_data:
        return None, appointments
    if "date" in availability_data:
        date = availability_data.get("date", None)
        date_obj = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
        return date_obj, appointments

    cdate = None
    availabilities = availability_data.get("availabilities", None)
    if availabilities is None:
        return None, appointments
    for date in availabilities:
        slots = availabilities.get(date, [])
        if not slots:
            continue
        for slot in slots:
            if slot not in appointments:
                appointments.append(slot)
            start_date = slot.get("start_time", None)
            if not start_date:
                continue
            tdate = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%f%z")
            if not cdate or tdate < cdate:
                cdate = tdate
    return cdate, appointments


def get_relevant_vaccine_specialties_id(specialties: dict) -> list:
    return [specialty_data.get("id") for specialty_data in specialties if is_specialty_relevant(specialty_data)]


def filter_vaccine_motives(
    session, selected_cabinet, id, vaccine_specialties, vaccine_cabinets, request: ScraperRequest = None
):
    if not id or not vaccine_specialties or not vaccine_cabinets:
        return None

    motive_categories = []
    vaccine_motives = []

    for specialty in vaccine_specialties:
        for cabinet in vaccine_cabinets:
            if selected_cabinet is not None and cabinet != selected_cabinet:
                continue
            if request:
                request.increase_request_count("motives")
            try:
                motive_req = session.get(API_KELDOC_MOTIVES.format(id, specialty, cabinet))
            except TimeoutException:
                continue
            motive_req.raise_for_status()
            motive_data = motive_req.json()
            motive_categories.extend(motive_data)

    for motive_cat in motive_categories:
        motives = motive_cat.get("motives", {})
        for motive in motives:
            motive_name = motive.get("name", None)
            if not motive_name or not is_appointment_relevant(motive_name):
                continue
            motive_agendas = [motive_agenda.get("id", None) for motive_agenda in motive.get("agendas", {})]
            vaccine_type = get_vaccine_name(motive_name)
            if vaccine_type is None:
                vaccine_type = get_vaccine_name(motive_cat.get("name"))
            vaccine_motives.append(
                {"id": motive.get("id", None), "vaccine_type": vaccine_type, "agendas": motive_agendas}
            )
    return vaccine_motives


# Filter by relevant appointments
def is_appointment_relevant(appointment_name: str) -> bool:
    if not appointment_name:
        return False

    appointment_name = appointment_name.lower()
    appointment_name = re.sub(" +", " ", appointment_name)
    for allowed_appointments in KELDOC_APPOINTMENT_REASON:
        if allowed_appointments in appointment_name:
            return True
    return False


# Filter by relevant specialties
def is_specialty_relevant(specialty_data: dict) -> bool:
    if not specialty_data:
        return False

    id = specialty_data.get("id", None)
    name = specialty_data.get("name", None)
    skills = specialty_data.get("skills", {})
    if not id or not name:
        return False
    for skill in skills:
        skill_name = skill.get("name", None)
        if not skill_name:
            continue
        if skill_name in KELDOC_COVID_SKILLS:
            return True
    for allowed_specialties in KELDOC_COVID_SPECIALTIES:
        if allowed_specialties == name:
            return True
    return False
