from urllib.parse import urlsplit, parse_qs

import httpx
from httpx import TimeoutException

from scraper.keldoc.keldoc_filters import parse_keldoc_availability
from scraper.keldoc.keldoc_routes import API_KELDOC_CALENDAR, API_KELDOC_CENTER, API_KELDOC_CABINETS

timeout = httpx.Timeout(15.0, connect=15.0)
session = httpx.Client(timeout=timeout)


class KeldocCenter:

    def __init__(self, base_url):
        self.base_url = base_url
        self.resource_params = None
        self.id = None
        self.specialties = None
        self.vaccine_specialties = None
        self.vaccine_cabinets = None
        self.vaccine_motives = None

    def fetch_vaccine_cabinets(self):
        if not self.id or not self.vaccine_specialties:
            return False

        self.vaccine_cabinets = []
        for specialty in self.vaccine_specialties:
            cabinet_url = API_KELDOC_CABINETS.format(self.id, specialty)
            try:
                cabinet_req = session.get(cabinet_url)
            except TimeoutException:
                continue
            cabinet_req.raise_for_status()
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
            resource = session.get(API_KELDOC_CENTER, params=self.resource_params)
        except TimeoutException:
            return False
        resource.raise_for_status()
        data = resource.json()

        self.id = data.get('id', None)
        self.specialties = data.get('specialties', None)
        return True

    def parse_resource(self):
        if not self.base_url:
            return False

        # Fetch new URL after redirection
        try:
            rq = session.get(self.base_url)
        except TimeoutException:
            return False
        rq.raise_for_status()
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
        self.resource_params = {
            'type': params_get.get('dom')[0],
            'location': params_get.get('inst')[0],
            'slug': params_get.get('user')[0]
        }
        return True

    def find_first_availability(self, start_date, end_date):
        if not self.vaccine_motives:
            return None

        # Find next availabilities
        first_availability = None
        for relevant_motive in self.vaccine_motives:
            if not 'id' in relevant_motive or not 'agendas' in relevant_motive:
                continue
            motive_id = relevant_motive.get('id', None)
            calendar_url = API_KELDOC_CALENDAR.format(motive_id)
            calendar_params = {
                'from': start_date,
                'to': end_date,
                'agenda_ids[]': relevant_motive.get('agendas', [])
            }
            try:
                calendar_req = session.get(calendar_url, params=calendar_params)
            except TimeoutException:
                # Some requests on Keldoc are taking too much time (for few centers)
                # and block the process completion.
                continue
            calendar_req.raise_for_status()

            date = parse_keldoc_availability(calendar_req.json())
            if date is None:
                continue
            # Compare first available date
            if first_availability is None or date < first_availability:
                first_availability = date
        return first_availability
