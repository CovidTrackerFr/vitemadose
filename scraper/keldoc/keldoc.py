from datetime import datetime, timedelta

import httpx

from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_specialties, filter_vaccine_motives
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling

timeout = httpx.Timeout(60.0, connect=60.0)
session = httpx.Client(timeout=timeout)

KELDOC_SLOT_LIMIT = 21


@Profiling.measure('keldoc_slot')
def fetch_slots(request: ScraperRequest):
    # Keldoc needs an end date, but if no appointment are found,
    # it still returns the next available appointment. Bigger end date
    # makes Keldoc responses slower.
    date_obj = datetime.strptime(request.get_start_date(), '%Y-%m-%d')
    end_date = (date_obj + timedelta(days=KELDOC_SLOT_LIMIT)).strftime('%Y-%m-%d')

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
    date, count = center.find_first_availability(request.get_start_date(), end_date)
    if not date:
        request.update_appointment_count(0)
        return None
    request.update_appointment_count(count)
    return date.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
