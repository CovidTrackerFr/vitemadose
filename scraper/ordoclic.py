import httpx
from httpx import TimeoutException
import json
from datetime import datetime, timedelta

timeout = httpx.Timeout(15.0, connect=15.0)
session = httpx.Client(timeout=timeout)

# get all slugs
def search():
    base_url = 'https://api.ordoclic.fr/v1/public/search'
    payload = {'page': '1', 'per_page': '500', 'in.isCovidVaccineSupported': 'true', 'in.isPublicProfile': 'true' }
    r = session.get(base_url, params=payload)
    r.raise_for_status()
    return(r.json())
  
def getReasons(entityId):
    base_url = 'https://api.ordoclic.fr/v1/solar/entities/{0}/reasons'.format(entityId)
    r = session.get(base_url)
    r.raise_for_status()
    return(r.json())

def getSlots(entityId, medicalStaffId, reasonId, start_date, end_date):
    base_url = 'https://api.ordoclic.fr/v1/solar/slots/availableSlots'
    payload = {"entityId": entityId, 
               "medicalStaffId": medicalStaffId, 
               "reasonId": reasonId,
               "dateEnd": "{0}T00:00:00.000Z".format(end_date), 
               "dateStart": "{0}T23:59:59.000Z".format(start_date)}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = session.post(base_url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()
    return(r.json())

def getProfile(rdv_site_web):
    base_url = 'https://api.ordoclic.fr/v1/public/entities/profile/{0}'
    base_url = base_url.format(rdv_site_web.rsplit('/', 1)[-1])
    r = session.get(base_url)
    r.raise_for_status()
    return(r.json())

def parse_ordoclic_slots(availability_data):
    start_date = None
    if not availability_data:
        return None
    if 'nextAvailableSlotDate' in availability_data:
        date = availability_data.get('nextAvailableSlotDate', None)
        if date == None:
            return None
        date_obj = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S%z')
        return date_obj

    availabilities = availability_data.get('slots', None)
    if availabilities is None:
        return None
    for slot in availabilities["slots"]:
        start_date = slot.get('timeStart', None)
        if not start_date:
            continue
        return datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%S.%f%z')
    return None
    
def fetch_centre_slots(rdv_site_web, start_date):
    first_availability = None
    profile = getProfile(rdv_site_web)
    slug = profile["profileSlug"]
    entityId = profile["entityId"]
    for professional in profile["publicProfessionals"]:
        medicalStaffId = professional["id"]
        name = professional["fullName"]
        zip = professional["zip"]
        reasons = getReasons(entityId)
        #reasonTypeId = 4 -> 1er Vaccin
        for reason in reasons["reasons"]:
            if reason["reasonTypeId"] == 4 and reason["canBookOnline"] == True: 
                reasonId = reason["id"]
                date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                slots = getSlots(entityId, medicalStaffId, reasonId, start_date, end_date)
                date = parse_ordoclic_slots(slots)
                if date is None:
                    continue
                if first_availability is None or date < first_availability:
                    first_availability = date
    return first_availability
