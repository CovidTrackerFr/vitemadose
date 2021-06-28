import requests
from urllib.parse import urlparse
import json
import pprint

JSON_PATH = "data/output/info_centres.json"
BLOCKLIST = "data/input/centers_blocklist.json"


def input_url():
    url_to_delete = input("\nEntrer l'url à bloquer :\n")
    return url_to_delete


def is_url_in_json(url_to_delete: str):
    url_in_json = False
    center_data = None
    url_path = urlparse(url_to_delete).path
    filtered_json = filter_urls()
    for centre in filtered_json:
        if url_path in centre["url"]:
            url_in_json = True
            center_data = centre
    return url_in_json, center_data


def filter_urls():
    new_centres = []
    with open(JSON_PATH) as file:
        centers_list = json.loads(file.read())
        for departement, centers in centers_list.items():
            for available in centers["centres_disponibles"]:
                new_centres.append(available)
            for unavailable in centers["centres_indisponibles"]:
                new_centres.append(unavailable)
    return new_centres


def update_json(center_data, github_issue, delete_reason):

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
    delete_reason_input = None
    github_issue_input = None

    print("\n******************* BLOCKLIST MANAGER *******************")
    print("Ce programme permet d'ajouter ou supprimer un centre à la Blocklist")

    url_to_delete = input_url()
    url_in_json, center_data = is_url_in_json(url_to_delete)

    if url_in_json:
        print(f'\n{center_data["nom"]}\n{center_data["metadata"]["address"]}\n{center_data["url"]}')
        question_yesno = lambda q: True if input(q).lower().strip()[-1] == "y" else False

        delete_confirmation = question_yesno("\nÊtes vous bien certain de vouloir supprimer ce centre ? (y/n)\n")
        if not delete_confirmation:
            print("[ERREUR] - Merci de réessayer.")
            exit(1)

        delete_reason_input = input("\nRaison de suppression ? (facultatif, utilisez entrée pour passer)\n")
        github_issue_input = input("\nLien issue github correspondante ? (facultatif, utilisez entrée pour passer)\n")
        delete_reason = delete_reason_input.strip() if len(delete_reason_input) > 0 else None
        github_issue = github_issue_input.strip() if len(github_issue_input) > 0 else None

        update_json(center_data, github_issue, delete_reason)
    else:
        print("[ERREUR] - Ce centre n'est pas présent dans nos fichiers.")
        exit(1)


if __name__ == "__main__":
    # execute only if run as a script
    main()
