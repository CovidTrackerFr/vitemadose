import json
import logging
from datetime import datetime

import pytz
import requests

from utils.vmd_config import get_conf_outstats

logger = logging.getLogger("scraper")

DATA_AUTO = get_conf_outstats().get("data-auto")


def compute_plateforme_data(centres_info):
    plateformes = {}
    center_types = {}

    for dep in centres_info:
        dep_data = centres_info[dep]
        centers = dep_data.get("centres_disponibles", {})
        centers.extend(dep_data.get("centres_indisponibles", {}))
        for centre_dispo in centers:

            plateforme = centre_dispo["plateforme"]
            if not plateforme:
                plateforme = "Autre"

            center_type = centre_dispo["type"]
            if not center_type:
                center_type = "Autre"

            next_app = centre_dispo.get("prochain_rdv", None)
            if plateforme not in plateformes:
                plateforme_data = {"disponible": 0, "total": 0, "creneaux": 0}
            else:
                plateforme_data = plateformes[plateforme]

            if center_type not in center_types:
                center_type_data = {"disponible": 0, "total": 0, "creneaux": 0}
            else:
                center_type_data = center_types[center_type]

            plateforme_data["disponible"] += 1 if next_app else 0
            plateforme_data["total"] += 1
            plateforme_data["creneaux"] += centre_dispo.get("appointment_count", 0)
            plateformes[plateforme] = plateforme_data

            center_type_data["disponible"] += 1 if next_app else 0
            center_type_data["total"] += 1
            center_type_data["creneaux"] += centre_dispo.get("appointment_count", 0)
            center_types[center_type] = center_type_data

    return plateformes, center_types


def generate_stats_center_types(centres_info):
    stats_path = get_conf_outstats().get("center_types")
    stats_data = {"dates": [], "plateformes": {}, "center_types": {}}

    try:
        history_rq = requests.get(f"{DATA_AUTO}{stats_path}")
        data = history_rq.json()
        if data:
            stats_data = data
    except Exception:
        logger.warning(f"Unable to fetch {DATA_AUTO}{stats_path}: generating a template file.")
    ctz = pytz.timezone("Europe/Paris")
    current_time = datetime.now(tz=ctz).strftime("%Y-%m-%d %H:00:00")
    if current_time in stats_data["dates"]:
        with open(f"data/output/{stats_path}", "w") as stat_graph_file:
            json.dump(stats_data, stat_graph_file)
        logger.info(f"Stats file already updated: {stats_path}")
        return

    if "center_types" not in stats_data:
        stats_data["center_types"] = {}

    stats_data["dates"].append(current_time)
    current_calc = compute_plateforme_data(centres_info)
    for plateforme in current_calc[0]:
        plateform_data = current_calc[0][plateforme]
        if plateforme not in stats_data["plateformes"]:
            stats_data["plateformes"][plateforme] = {
                "disponible": [plateform_data["disponible"]],
                "total": [plateform_data["total"]],
                "creneaux": [plateform_data["creneaux"]],
            }
            continue
        current_data = stats_data["plateformes"][plateforme]
        current_data["disponible"].append(plateform_data["disponible"])
        current_data["total"].append(plateform_data["total"])
        current_data["creneaux"].append(plateform_data["creneaux"])

    for center_type in current_calc[1]:
        center_type_data = current_calc[1][center_type]
        if center_type not in stats_data["center_types"]:
            stats_data["center_types"][center_type] = {
                "disponible": [center_type_data["disponible"]],
                "total": [center_type_data["total"]],
                "creneaux": [center_type_data["creneaux"]],
            }
            continue
        current_data = stats_data["center_types"][center_type]
        current_data["disponible"].append(center_type_data["disponible"])
        current_data["total"].append(center_type_data["total"])
        current_data["creneaux"].append(center_type_data["creneaux"])

    with open(f"data/output/{stats_path}", "w") as stat_graph_file:
        json.dump(stats_data, stat_graph_file)
    logger.info(f"Updated stats file: {stats_path}")
