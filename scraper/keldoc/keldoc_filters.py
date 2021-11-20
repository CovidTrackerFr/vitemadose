import re
import logging
from datetime import datetime

from httpx import TimeoutException
from scraper.keldoc.keldoc_routes import API_KELDOC_MOTIVES
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from utils.vmd_config import get_conf_platform, get_config
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
import dateutil

logger = logging.getLogger("scraper")
KELDOC_CONF = get_conf_platform("keldoc")
KELDOC_FILTERS = KELDOC_CONF.get("filters", {})

KELDOC_COVID_SPECIALTIES = KELDOC_FILTERS.get("appointment_speciality", [])

KELDOC_APPOINTMENT_REASON = KELDOC_FILTERS.get("appointment_reason", [])

KELDOC_COVID_SKILLS = KELDOC_FILTERS.get("appointment_skill", [])

MAX_DOSE_IN_JSON = get_config().get("max_dose_in_classic_jsons")


def parse_keldoc_availability(self, availability_data, appointments, vaccine=None, dose=None):
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
            self.found_creneau(
                Creneau(
                    horaire=dateutil.parser.parse(slot["start_time"]),
                    reservation_url=self.base_url,
                    type_vaccin=[vaccine],
                    lieu=self.lieu,
                    dose=dose,
                )
            )
    return cdate, appointments


def filter_vaccine_motives(center_motives):
    if not center_motives:
        return None
    vaccine_motives = []
    for motive_cat in center_motives:
        motives = motive_cat.get("motives", {})
        for motive in motives:
            motive_name = motive.get("name", None)
            appointment_relevant, dose = is_appointment_relevant(motive_name)

            if not motive_name or not appointment_relevant:
                continue
            motive_agendas = [motive_agenda.get("id", None) for motive_agenda in motive.get("agendas", {})]
            vaccine_type = get_vaccine_name(motive_name)
            if vaccine_type is None:
                vaccine_type = get_vaccine_name(motive_cat.get("name"))

            vaccine_motives.append(
                {"id": motive.get("id", None), "vaccine_type": vaccine_type, "agendas": motive_agendas, "dose": dose}
            )
    return vaccine_motives


# Filter by relevant appointments
def is_appointment_relevant(appointment_name: str) -> bool:
    if not appointment_name:
        return False, 0

    dose = keldoc_dose_number(appointment_name)
    if not dose:
        return False, 0

    if dose <= MAX_DOSE_IN_JSON:
        return True, dose

    return False, 0


def keldoc_dose_number(motive):

    if any([tag.lower() in motive.lower() for tag in KELDOC_FILTERS.get("rappel_filter")]) and not any(
        [tag.lower() in motive.lower() for tag in KELDOC_FILTERS.get("immuno_filter")]
    ):
        dose = 3
        return dose

    if any([tag.lower() in motive.lower() for tag in KELDOC_FILTERS.get("dose2_filter")]):
        dose = 2
        return dose

    if any([tag.lower() in motive.lower() for tag in KELDOC_FILTERS.get("dose1_filter")]):
        dose = 1
        return dose


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
