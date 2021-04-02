import json
import requests
import datetime
from bs4 import BeautifulSoup

from prototype import centre_iterator

def fetch_maiia_slots(rdv_site_web, from_date_str, to_date_str):
    try:
        response = requests.get(rdv_site_web)
        soup = BeautifulSoup(response.text, 'html.parser')
        print(response.status_code)
        rdv_form = soup.find('script', {'type' : 'application/json'}, text=True)
        if rdv_form:
            earliest_date = datetime.datetime.max
            json_form = json.loads(str(rdv_form.contents[0]))
            center_infos = json_form['props']['initialState']['cards']['item']['center']
            root_center_id = center_infos['id']
            specialty_id = center_infos['practitioners'][0]['speciality']['id']
            practitioner_id = center_infos['practitioners'][0]['id']

            # Retrieve consultation reasons
            response = requests.get(f'https://www.maiia.com/api/pat-public/consultation-reason-hcd?limit=200&page=0&rootCenterId={root_center_id}&specialityId={specialty_id}')
            
            json_resp = json.loads(response.text)
            for item in json_resp['items']:
                item_id = item['id']
                response = requests.get(f'https://www.maiia.com/api/pat-public/availabilities?centerId={root_center_id}&consultationReasonId={item_id}&from={from_date_str}&limit=1440&page=0&practitionerId={practitioner_id}&to={to_date_str}')
                for availability in json.loads(response.text)['items']:
                    availability_date = datetime.datetime.strptime(availability['startDateTime'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    if availability_date < earliest_date:
                        earliest_date = availability_date
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(e, rdv_site_web)
    return earliest_date

def get_available_centres():
    centres = {}
    from_date = datetime.datetime.now()
    to_date = from_date + datetime.timedelta(days=30)
    from_date_str = from_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    to_date_str = to_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    for row in centre_iterator():
        if 'maiia' in row['rdv_site_web']:
            cp_start = row['com_cp'][:2]
            if int(cp_start) == 97:
                cp_start = row['com_cp'][:3]
            if cp_start not in centres:
                centres[cp_start] = {
                    'version': 1,
                    'centres_disponibles': [],
                    'centres_indisponibles': []
                }
            earliest_date = fetch_maiia_slots(row['rdv_site_web'], from_date_str, to_date_str)
            if earliest_date != datetime.datetime.max:
                centres[cp_start]['centres_disponibles'].append({
                    'nom': row['nom'],
                    'url': row['rdv_site_web'],
                    'prochain_rdv': earliest_date.strftime('%Y-%m-%d %H:%M'),
                    'plateforme': 'Maiia'
                })
            else:
                centres[cp_start]['centres_indisponibles'].append({
                    'nom': row['nom'],
                    'url': row['rdv_site_web'],
                    'plateforme': 'Maiia'
                })
    for depart, depart_centres in centres.items():
        with open(f'output/{depart}.json', 'w') as outfile:
            json.dump(depart_centres, outfile)

if __name__ == '__main__':
    get_available_centres()
    