import json
import requests
import csv
import io
from tmp.utils.vmd_utils import fix_scrap_urls


def load_centres_gvt():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')

    return [fix_scrap_urls(row["rdv_site_web"]) for row in csvreader]

path_results = "tmp/data/output"

departements_names = [str(i).zfill(2) for i in range(1,96)] + ["972", "973", "974", "976", "2A", "2B"]
departements_names.remove("20")

path_centers_open_data = "tmp/data/output/centres_open_data.json"

links_centers_open_data = load_centres_gvt()


nb_dispos_gov_total = 0
nb_dispos_total = 0

for departement in departements_names:
    data_vmd = json.load(open(f"{path_results}/{departement}.json"))
    centres_disponibles = data_vmd["centres_disponibles"]
    nb_dispos_gov = len([c for c in centres_disponibles if c["url"] in links_centers_open_data])
    print(f"{departement} {nb_dispos_gov}/{len(centres_disponibles)}")
    nb_dispos_gov_total += nb_dispos_gov
    nb_dispos_total += len(centres_disponibles)


print(f"TOTAL {nb_dispos_gov_total}/{nb_dispos_total}")


for departement in departements_names:
    data_vmd = json.load(open(f"{path_results}/{departement}.json"))
    centres_disponibles = data_vmd["centres_indisponibles"]
    nb_dispos_gov = len([c for c in centres_disponibles if c["url"] in links_centers_open_data])
    print(f"{departement} {nb_dispos_gov}/{len(centres_disponibles)}")
    nb_dispos_gov_total += nb_dispos_gov
    nb_dispos_total += len(centres_disponibles)


print(f"TOTAL {nb_dispos_gov_total}/{nb_dispos_total}")