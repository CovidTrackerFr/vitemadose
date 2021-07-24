import logging
import os
import time
from math import floor
from typing import Optional, Union, Iterable, List
from urllib.parse import urlsplit, parse_qs
import datetime as dt
from dateutil.parser import isoparse
from pytz import timezone
import httpx
from scraper.keldoc.keldoc_filters import parse_keldoc_availability, filter_vaccine_motives
from scraper.keldoc.keldoc_routes import API_KELDOC_CALENDAR, API_KELDOC_CENTER, API_KELDOC_CABINETS
from scraper.pattern.scraper_request import ScraperRequest
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import DummyQueue

KELDOC_CONF = get_conf_platform("keldoc")
timeout = httpx.Timeout(KELDOC_CONF.get("timeout", 25), connect=KELDOC_CONF.get("timeout", 25))
KELDOC_HEADERS = {
    "User-Agent": os.environ.get("KELDOC_API_KEY", ""),
}
# 16 days is enough for now, due to recent issues with Keldoc API
KELDOC_SLOT_PAGES = KELDOC_CONF.get("pagination", {}).get("pages", 2)
KELDOC_DAYS_PER_PAGE = KELDOC_CONF.get("pagination", {}).get("days", 4)
KELDOC_SLOT_TIMEOUT = KELDOC_CONF.get("timeout", 20)
DEFAULT_CLIENT = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)
logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")


class KeldocCenter:
    def __init__(self, request: ScraperRequest, client: httpx.Client = None, creneau_q=DummyQueue):
        self.request = request
        self.base_url = request.get_url()
        self.client = DEFAULT_CLIENT if client is None else client
        self.id = None
        self.vaccine_motives = None
        self.appointment_motives = request.input_data
        self.creneau_q = creneau_q
        self.lieu = None

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def get_timetables(
        self,
        start_date: dt.datetime,
        motive_id: str,
        agenda_ids: List[int],
        page: int = 1,
        timetable=None,
        run: float = 0,
    ) -> Iterable[Union[Optional[dict], float]]:
        """
        Get timetables recursively with KELDOC_DAYS_PER_PAGE as the number of days to query.
        Recursively limited by KELDOC_SLOT_PAGES and appends new availabilities to a ’timetable’,
        freshly initialized at the beginning.
        Uses date as a reference for next availability and in order to avoid useless requests when
        we already know if a timetable is empty.
        """
        start_time = time.time()
        if timetable is None:
            timetable = {}
        if run >= KELDOC_SLOT_TIMEOUT:
            return timetable, run
        calendar_url = API_KELDOC_CALENDAR.format(motive_id)

        end_date = (start_date + dt.timedelta(days=KELDOC_DAYS_PER_PAGE)).strftime("%Y-%m-%d")
        logger.debug(
            f"get_timetables -> start_date: {start_date} end_date: {end_date} "
            f"motive: {motive_id} agenda: {agenda_ids} (page: {page})"
        )
        calendar_params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date,
            "agenda_ids[]": agenda_ids,
        }
        self.request.increase_request_count("slots")
        try:
            calendar_req = self.client.get(calendar_url, params=calendar_params)
            calendar_req.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(
                f"Keldoc request timed out for center: {self.base_url} (calendar request)"
                f" celendar_url: {calendar_url}"
                f" calendar_params: {calendar_params}"
            )
            self.request.increase_request_count("time-out")
            return timetable, run

        except httpx.HTTPStatusError as hex:
            logger.warning(
                f"Keldoc request returned error {hex.response.status_code} "
                f"for center: {self.base_url} (calendar request)"
            )
            self.request.increase_request_count("error")
            return timetable, run

        except (httpx.RemoteProtocolError, httpx.ConnectError) as hex:
            logger.warning(f"Keldoc raise error {hex} for center: {self.base_url} (calendar request)")
            self.request.increase_request_count("error")
            return timetable, run
        current_timetable = calendar_req.json()
        run += time.time() - start_time
        # No fresh timetable
        if not current_timetable:
            return timetable, run
        # Get the first date only
        if "date" in current_timetable:
            if "date" not in timetable:
                timetable["date"] = current_timetable.get("date")
            """
            Optimize query count by jumping directly to the first availability date by using ’date’ key
            Checks for the presence of the ’availabilities’ attribute, even if it's not supposed to be set
            """
            if "availabilities" not in current_timetable:
                next_expected_date = start_date + dt.timedelta(days=KELDOC_DAYS_PER_PAGE)
                next_fetch_date = isoparse(current_timetable["date"])
                diff = next_fetch_date.replace(tzinfo=None) - next_expected_date.replace(tzinfo=None)

                if page >= KELDOC_SLOT_PAGES or run >= KELDOC_SLOT_TIMEOUT:
                    return timetable, run
                return self.get_timetables(
                    next_fetch_date,
                    motive_id,
                    agenda_ids,
                    1 + max(0, floor(diff.days / KELDOC_DAYS_PER_PAGE)) + page,
                    timetable,
                    run,
                )

        # Insert availabilities
        if "availabilities" in current_timetable:
            if "availabilities" not in timetable:
                timetable["availabilities"] = current_timetable.get("availabilities")
            else:
                timetable["availabilities"].update(current_timetable.get("availabilities"))
        # Pop date because it prevents availability count
        if timetable.get("availabilities") and timetable.get("date"):
            timetable.pop("date")

        if page >= KELDOC_SLOT_PAGES or run >= KELDOC_SLOT_TIMEOUT:
            return timetable, run
        return self.get_timetables(
            start_date + dt.timedelta(days=KELDOC_DAYS_PER_PAGE), motive_id, agenda_ids, 1 + page, timetable, run
        )

    def count_appointements(self, appointments: list, start_date: str, end_date: str) -> int:
        paris_tz = timezone("Europe/Paris")
        start_dt = isoparse(start_date).astimezone(paris_tz)
        end_dt = isoparse(end_date).astimezone(paris_tz)
        count = 0

        for appointment in appointments:
            slot_dt = isoparse(appointment["start_time"]).astimezone(paris_tz)
            if start_dt <= slot_dt < end_dt:
                count += 1

        logger.debug(f"Slots count from {start_date} to {end_date}: {count}")
        return count

    def find_first_availability(self, start_date: str):
        if not self.vaccine_motives:
            return None, 0
        # Find next availabilities
        first_availability = None
        appointments = []
        for relevant_motive in self.vaccine_motives:
            if "id" not in relevant_motive or "agendas" not in relevant_motive:
                continue
            motive_id = relevant_motive.get("id", None)
            vaccine = relevant_motive.get("vaccine_type")
            agenda_ids = relevant_motive.get("agendas", None)
            if not agenda_ids:
                continue
            timetables, runtime = self.get_timetables(isoparse(start_date), motive_id, agenda_ids)
            logger.debug(
                f"get_timetables -> result [motive: {motive_id} agenda: {agenda_ids}] -> runtime: {round(runtime, 2)}s"
            )
            date, appointments = parse_keldoc_availability(self, timetables, appointments, vaccine)
            if date is None:
                continue
            self.request.add_vaccine_type(vaccine)
            # Compare first available date
            if first_availability is None or date < first_availability:
                first_availability = date
            if not timetables or "availabilities" not in timetables:
                continue
        return first_availability, len(appointments)
