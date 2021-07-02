import requests
from urllib.parse import urlparse
import json
import os


BLOCKLIST = "data/input/centers_blocklist.json"
GITLAB_CENTERS = f"https://vitemadose.gitlab.io/vitemadose/info_centres.json"


def input_data():
    name = os.environ.get("INPUT_NAME_TO_DELETE", "")
    zipcode = os.environ.get("INPUT_ZIPCODE_TO_DELETE", "")
    return name, zipcode


def is_url_in_json(name: str, zipcode: str):
    url_in_json = False
    center_data = None
    if not name or not zipcode:
        print("[ERREUR] - Le nom ou le code postal n'ont pas été saisis correctement.")
        exit(1)
    filtered_json = filter_urls()
    for centre in filtered_json:
        if name.strip() == centre["nom"].strip() and zipcode.strip() in centre["location"]["cp"]:
            url_in_json = True
            center_data = centre
    if center_data:
        print(
            f'\nLe centre choisi est \n {center_data["nom"]}\n{center_data["url"]}\n{center_data["metadata"]["address"]}'
        )
    else:
        print("[ERREUR] - Aucun centre ne correspond à votre recherche.")
        exit(1)
    return url_in_json, center_data


def filter_urls():
    new_centres = []
    response = requests.get(GITLAB_CENTERS)
    response.raise_for_status()
    centers_list = response.json()

    for departement, centers in centers_list.items():
        for available in centers["centres_disponibles"]:
            new_centres.append(available)
        for unavailable in centers["centres_indisponibles"]:
            new_centres.append(unavailable)
    return new_centres


def update_json(center_data: dixt, github_issue: str, delete_reason: str):

    url_path = urlparse(center_data["url"]).path

    with open(BLOCKLIST, "r+") as blocklist_file:

        data = json.load(blocklist_file)
        new_center = {
            "name": center_data["nom"],
            "url": center_data["url"],
            "issue": github_issue,
            "details": delete_reason,
        }
        for blocked_center in data["centers_not_displayed"]:
            if url_path in blocked_center["url"]:
                print("[ERREUR] - Le centre est déjà bloqué.")
                exit(1)
        data["centers_not_displayed"].append(new_center)
        blocklist_file.seek(0)
        json.dump(data, blocklist_file, indent=2)
        print("\n[SUCCESS] - Le centre a bien été ajouté à la blocklist !\n")


def main():
    delete_reason = None
    github_issue = None
    print("\n******************* BLOCKLIST MANAGER *******************")
    print("Ce programme permet d'ajouter un centre à la Blocklist")
    name, zipcode = input_data()
    url_in_json, center_data = is_url_in_json(name, zipcode)
    if url_in_json:
        delete_reason = os.environ.get("INPUT_DELETE_REASON", "").strip()
        github_issue = os.environ.get("INPUT_GIT_ISSUE", "").strip()
        if len(delete_reason) == 0:
            delete_reason = None
        if len(github_issue) == 0:
            github_issue = None
        update_json(center_data, github_issue, delete_reason)
    else:
        print("[ERREUR] - Ce centre n'est pas présent dans nos fichiers.")
        exit(1)


if __name__ == "__main__":
    # execute only if run as a script
    main()
