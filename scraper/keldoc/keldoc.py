from datetime import datetime, timedelta

import httpx

from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_specialties, filter_vaccine_motives

timeout = httpx.Timeout(30.0, connect=30.0)
session = httpx.Client(timeout=timeout)


def fetch_slots(base_url, start_date):
    # Keldoc needs an end date, but if no appointment are found,
    # it still returns the next available appointment. Bigger end date
    # makes Keldoc responses slower.
    date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

    center = KeldocCenter(base_url=base_url, client=session)
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
    date = center.find_first_availability(start_date, end_date)
    if not date:
        return None
    return date.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
