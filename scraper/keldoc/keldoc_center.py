import logging
import os
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import httpx

from scraper.keldoc.keldoc_filters import parse_keldoc_availability
from scraper.keldoc.keldoc_routes import API_KELDOC_CALENDAR, API_KELDOC_CENTER, API_KELDOC_CABINETS
from scraper.pattern.scraper_request import ScraperRequest

timeout = httpx.Timeout(10.0, connect=10.0)
KELDOC_HEADERS = {
    'User-Agent': os.environ.get('KELDOC_API_KEY', ''),
}
KELDOC_SLOT_LIMIT = 7
DEFAULT_CLIENT = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)
logger = logging.getLogger('scraper')


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
                logger.warning(f"Keldoc request returned error {hex.response.status_code} "
                               f"for center: {self.base_url} (vaccine cabinets)")
                continue
            data = cabinet_req.json()
            if not data:
                continue
            self.vaccine_cabinets.extend([cabinet.get('id', None) for cabinet in data])
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
            logger.warning(f"Keldoc request returned error {hex.response.status_code} "
                           f"for center: {self.base_url} (center info)")
            return False
        data = resource.json()

        self.id = data.get('id', None)
        self.specialties = data.get('specialties', None)
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
            logger.warning(f"Keldoc request returned error {hex.response.status_code} "
                           f"for center: {self.base_url} (resource)")
            return False
        new_url = rq.url._uri_reference.unsplit()

        # Parse relevant GET params for Keldoc API requests
        query = urlsplit(new_url).query
        params_get = parse_qs(query)
        mandatory_params = ['dom', 'inst', 'user']
        # Some vaccination centers on Keldoc do not
        # accept online appointments, so you cannot retrieve data
        for mandatory_param in mandatory_params:
            if not mandatory_param in params_get:
                return False
        # If the vaccination URL have several medication places,
        # we select the current cabinet, since CSV data contains subURLs
        self.selected_cabinet = params_get.get('cabinet', [None])[0]
        if self.selected_cabinet:
            self.selected_cabinet = int(self.selected_cabinet)
        self.resource_params = {
            'type': params_get.get('dom')[0],
            'location': params_get.get('inst')[0],
            'slug': params_get.get('user')[0]
        }
        return True

    
    def get_timetables(self, start_date, motive_id, agenda_id):
        # Keldoc needs an end date, but if no appointment are found,
        # it still returns the next available appointment. Bigger end date
        # makes Keldoc responses slower.
        calendar_url = API_KELDOC_CALENDAR.format(motive_id)
        calendar_params = {
            'from': start_date,
            'to': start_date,
            'agenda_ids[]': agenda_id
        }
        try:
            calendar_req = self.client.get(calendar_url, params=calendar_params)
            calendar_req.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"Keldoc request timed out for center: {self.base_url} (calendar request)"
                f' calendar_url: {calendar_url}'
                f' calendar_params: {calendar_params}')
            return None
        except httpx.HTTPStatusError as hex:
            logger.warning(f"Keldoc request returned error {hex.response.status_code} "
                        f"for center: {self.base_url} (calendar request)")
            return None
        calendar_json = calendar_req.json()
        if 'date' in calendar_json:
            new_date = isoparse(calendar_json['date'])
            start_date = new_date.strftime('%Y-%m-%d')
        end_date = (isoparse(start_date) + timedelta(days=KELDOC_SLOT_LIMIT)).strftime('%Y-%m-%d')
        calendar_params = {
            'from': start_date,
            'to': end_date,
            'agenda_ids[]': agenda_id
        }
        try:
            calendar_req = self.client.get(calendar_url, params=calendar_params)
            calendar_req.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"Keldoc request timed out for center: {self.base_url} (calendar request)"
                f' celendar_url: {calendar_url}'
                f' calendar_params: {calendar_params}')
            return None
        except httpx.HTTPStatusError as hex:
            logger.warning(f"Keldoc request returned error {hex.response.status_code} "
                        f"for center: {self.base_url} (calendar request)")
            return None
        return calendar_req.json()


    def find_first_availability(self, start_date):
        if not self.vaccine_motives:
            return None, 0

        # Find next availabilities
        first_availability = None
        appointments = []
        for relevant_motive in self.vaccine_motives:
            if 'id' not in relevant_motive or 'agendas' not in relevant_motive:
                continue
            motive_id = relevant_motive.get('id', None)
            calendar_url = API_KELDOC_CALENDAR.format(motive_id)

            for agenda_id in relevant_motive.get('agendas', []):
                timetables = self.get_timetables(start_date, motive_id, agenda_id)
                date, appointments = parse_keldoc_availability(timetables, appointments)
                if date is None:
                    continue
                self.request.add_vaccine_type(relevant_motive.get('vaccine_type'))
                # Compare first available date
                if first_availability is None or date < first_availability:
                    first_availability = date
        return first_availability, len(appointments)
