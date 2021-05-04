import logging
import os
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone
import httpx

from scraper.keldoc.keldoc_filters import parse_keldoc_availability
from scraper.keldoc.keldoc_routes import API_KELDOC_CALENDAR, API_KELDOC_CENTER, API_KELDOC_CABINETS
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import INTERVAL_SPLIT_DAYS

timeout = httpx.Timeout(25.0, connect=25.0)
KELDOC_HEADERS = {
    "User-Agent": os.environ.get("KELDOC_API_KEY", ""),
}
KELDOC_SLOT_LIMIT = 50
DEFAULT_CLIENT = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)
logger = logging.getLogger("scraper")


class KeldocCenter:
    def __init__(self, request: ScraperRequest, client: httpx.Client = None):
        self.request = request
        self.base_url = request.get_url()
        self.client = DEFAULT_CLIENT if client is None else client
        self.resource_params = None
        self.id = None
        self.specialties = None
        self.vaccine_specialties = None
        self.vaccine_cabinets = None
        self.vaccine_motives = None
        self.selected_cabinet = None

    def fetch_vaccine_cabinets(self):
        if not self.id or not self.vaccine_specialties:
            return False
        self.vaccine_cabinets = []
        for specialty in self.vaccine_specialties:
            cabinet_url = API_KELDOC_CABINETS.format(self.id, specialty)
            try:
                cabinet_req = self.client.get(cabinet_url)
                cabinet_req.raise_for_status()
            except httpx.TimeoutException as hex:
                logger.warning(f"Keldoc request timed out for center: {self.base_url} (vaccine cabinets)")
                continue
            except httpx.HTTPStatusError as hex:
                logger.warning(
                    f"Keldoc request returned error {hex.response.status_code} "
                    f"for center: {self.base_url} (vaccine cabinets)"
                )
                continue
            data = cabinet_req.json()
            if not data:
                continue
            self.vaccine_cabinets.extend([cabinet.get("id", None) for cabinet in data])
        return self.vaccine_cabinets

    def fetch_center_data(self):
        if not self.base_url:
            return False
        # Fetch center id
        try:
            resource = self.client.get(API_KELDOC_CENTER, params=self.resource_params)
            resource.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"Keldoc request timed out for center: {self.base_url} (center info)")
            return False
        except httpx.HTTPStatusError as hex:
            logger.warning(
                f"Keldoc request returned error {hex.response.status_code} "
                f"for center: {self.base_url} (center info)"
            )
            return False
        data = resource.json()

        self.id = data.get("id", None)
        self.specialties = data.get("specialties", None)
        return True

    def parse_resource(self):
        if not self.base_url:
            return False

        # Fetch new URL after redirection
        try:
            rq = self.client.get(self.base_url)
            rq.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"Keldoc request timed out for center: {self.base_url} (resource)")
            return False
        except httpx.HTTPStatusError as hex:
            logger.warning(
                f"Keldoc request returned error {hex.response.status_code} " f"for center: {self.base_url} (resource)"
            )
            return False
        new_url = rq.url._uri_reference.unsplit()

        # Parse relevant GET params for Keldoc API requests
        query = urlsplit(new_url).query
        params_get = parse_qs(query)
        mandatory_params = ["dom", "inst", "user"]
        # Some vaccination centers on Keldoc do not
        # accept online appointments, so you cannot retrieve data
        for mandatory_param in mandatory_params:
            if not mandatory_param in params_get:
                return False
        # If the vaccination URL have several medication places,
        # we select the current cabinet, since CSV data contains subURLs
        self.selected_cabinet = params_get.get("cabinet", [None])[0]
        if self.selected_cabinet:
            self.selected_cabinet = int(self.selected_cabinet)
        self.resource_params = {
            "type": params_get.get("dom")[0],
            "location": params_get.get("inst")[0],
            "slug": params_get.get("user")[0],
        }
        return True

    def get_timetables(self, start_date, motive_id, agenda_ids):
        # Keldoc needs an end date, but if no appointment are found,
        # it still returns the next available appointment. Bigger end date
        # makes Keldoc responses slower.
        calendar_url = API_KELDOC_CALENDAR.format(motive_id)
        end_date = (isoparse(start_date) + timedelta(days=KELDOC_SLOT_LIMIT)).strftime("%Y-%m-%d")
        logger.debug(
            f"get_timetables -> start_date: {start_date} end_date: {end_date} motive: {motive_id} agenda: {agenda_ids}"
        )
        calendar_params = {
            "from": start_date,
            "to": end_date,
            "agenda_ids[]": "&agenda_ids[]".join(str(agenda_id) for agenda_id in agenda_ids),
        }
        try:
            calendar_req = self.client.get(calendar_url, params=calendar_params)
            calendar_req.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(
                f"Keldoc request timed out for center: {self.base_url} (calendar request)"
                f" celendar_url: {calendar_url}"
                f" calendar_params: {calendar_params}"
            )
            return None
        except httpx.HTTPStatusError as hex:
            logger.warning(
                f"Keldoc request returned error {hex.response.status_code} "
                f"for center: {self.base_url} (calendar request)"
            )
            return None
        return calendar_req.json()

    def count_appointements(self, appointments: list, start_date: str, end_date: str) -> int:
        paris_tz = timezone("Europe/Paris")
        start_dt = isoparse(start_date).astimezone(paris_tz)
        end_dt = isoparse(end_date).astimezone(paris_tz)
        count = 0

        for appointment in appointments:
            slot_dt = isoparse(appointment["start_time"]).astimezone(paris_tz)
            if slot_dt >= start_dt and slot_dt < end_dt:
                count += 1

        logger.debug(f"Slots count from {start_date} to {end_date}: {count}")
        return count

    def find_first_availability(self, start_date: str):
        if not self.vaccine_motives:
            return None, 0, None

        # Find next availabilities
        first_availability = None
        appointments = []
        appointment_schedules = {}
        for n in INTERVAL_SPLIT_DAYS:
            appointment_schedules[f"{n}_days"] = 0
        for relevant_motive in self.vaccine_motives:
            if "id" not in relevant_motive or "agendas" not in relevant_motive:
                continue
            motive_id = relevant_motive.get("id", None)
            calendar_url = API_KELDOC_CALENDAR.format(motive_id)

            agenda_ids = relevant_motive.get("agendas", None)
            if not agenda_ids:
                continue
            timetables = self.get_timetables(start_date, motive_id, agenda_ids)
            date, appointments = parse_keldoc_availability(timetables, appointments)
            if date is None:
                continue
            self.request.add_vaccine_type(relevant_motive.get("vaccine_type"))
            # Compare first available date
            if first_availability is None or date < first_availability:
                first_availability = date
            if not timetables or "availabilities" not in timetables:
                continue
        # update appointment_schedules
        for n in INTERVAL_SPLIT_DAYS:
            n_date = (isoparse(start_date) + timedelta(days=n)).isoformat()
            appointment_schedules[f"{n}_days"] += self.count_appointements(appointments, start_date, n_date)
        return first_availability, len(appointments), appointment_schedules
