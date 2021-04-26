import os
from datetime import datetime, timedelta

import httpx

from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_specialties, filter_vaccine_motives
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling

timeout = httpx.Timeout(25.0, connect=25.0)
KELDOC_HEADERS = {
    'User-Agent': os.environ.get('KELDOC_API_KEY', ''),
}
session = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)


@Profiling.measure('keldoc_slot')
def fetch_slots(request: ScraperRequest):
    center = KeldocCenter(request, client=session)
    # Unable to parse center resources (id, location)?
    if not center.parse_resource():
        return None
    # Try to fetch center data
    if not center.fetch_center_data():
        return None

    # Filter specialties, cabinets & motives
    center.vaccine_specialties = filter_vaccine_specialties(center.specialties)
    center.fetch_vaccine_cabinets()
    center.vaccine_motives = filter_vaccine_motives(session, center.selected_cabinet, center.id,
                                                    center.vaccine_specialties, center.vaccine_cabinets)
    # Find the first availability
    date, count = center.find_first_availability(request.get_start_date())
    if not date:
        request.update_appointment_count(0)
        return None
    request.update_appointment_count(count)
    return date.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
