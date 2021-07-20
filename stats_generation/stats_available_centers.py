import json
import logging
from datetime import datetime

import pytz
import requests

from pathlib import Path
from stats_generation.stats_center_types import generate_stats_center_types
from stats_generation.stats_map import make_maps
from utils.vmd_config import get_conf_outstats, get_conf_outputs
from utils.vmd_logger import enable_logger_for_production

logger = logging.getLogger("scraper")

DATA_AUTO = get_conf_outstats().get("data-auto")


def generate_stats_date(centres_stats):
    stats_path = get_conf_outstats().get("by_date")
    stats_data = {
        "dates": [],
        "total_centres_disponibles": [],
        "total_centres": [],
        "total_appointments": [],
    }

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
        with open(Path("data", "output", stats_path), "w") as stat_graph_file:
            json.dump(stats_data, stat_graph_file)
        logger.info(f"Stats file already updated: {stats_path}")
        return
    data_alldep = centres_stats["tout_departement"]
    stats_data["dates"].append(current_time)
    stats_data["total_centres_disponibles"].append(data_alldep["disponibles"])
    stats_data["total_centres"].append(data_alldep["total"])
    stats_data["total_appointments"].append(data_alldep["creneaux"])

    with open(Path("data", "output", stats_path), "w") as stat_graph_file:
        json.dump(stats_data, stat_graph_file)
    logger.info(f"Updated stats file: {stats_path}")


def generate_stats_dep_date(centres_stats):
    stats_path = get_conf_outstats().get("by_date_dep")
    stats_data = {
        "dates": [],
        "dep_centres_disponibles": {},
        "dep_centres": {},
        "dep_appointments": {},
    }

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
        with open(Path("data", "output", stats_path), "w") as stat_graph_file:
            json.dump(stats_data, stat_graph_file)
        logger.info(f"Stats file already updated: {stats_path}")
        return
    stats_data["dates"].append(current_time)

    for dep in centres_stats:
        if dep == "tout_departement":
            continue
        if dep not in stats_data["dep_centres_disponibles"]:
            stats_data["dep_centres_disponibles"][dep] = []
        if dep not in stats_data["dep_centres"]:
            stats_data["dep_centres"][dep] = []
        if dep not in stats_data["dep_appointments"]:
            stats_data["dep_appointments"][dep] = []
        dep_data = centres_stats[dep]
        stats_data["dep_centres_disponibles"][dep].append(dep_data["disponibles"])
        stats_data["dep_centres"][dep].append(dep_data["total"])
        stats_data["dep_appointments"][dep].append(dep_data["creneaux"])

    with open(Path("data", "output", stats_path), "w") as stat_graph_file:
        json.dump(stats_data, stat_graph_file)
    logger.info(f"Updated stats file: {stats_path}")


def export_centres_stats(
    center_data=Path(get_conf_outputs().get("last_scans")), stats_path=get_conf_outstats().get("global")
):

    if center_data.exists():
        centres_info = get_centres_info(center_data)
        centres_stats = {"tout_departement": {"disponibles": 0, "total": 0, "creneaux": 0}}

        tout_dep_obj = centres_stats["tout_departement"]

        for dep_code, dep_value in centres_info.items():
            nombre_disponibles = len(dep_value["centres_disponibles"])
            count = len(dep_value["centres_indisponibles"]) + nombre_disponibles
            creneaux = sum([center.get("appointment_count", 0) for center in dep_value["centres_disponibles"]])

            centres_stats[dep_code] = {
                "disponibles": nombre_disponibles,
                "total": count,
                "creneaux": creneaux,
            }

            tout_dep_obj["disponibles"] += nombre_disponibles
            tout_dep_obj["total"] += count
            tout_dep_obj["creneaux"] += creneaux

        available_pct = (tout_dep_obj["disponibles"] / max(1, tout_dep_obj["total"])) * 100
        logger.info(
            "Found {0}/{1} available centers. ({2}%)".format(
                tout_dep_obj["disponibles"],
                tout_dep_obj["total"],
                round(available_pct, 2),
            )
        )
        with open(Path("data", "output", stats_path), "w") as stats_file:
            json.dump(centres_stats, stats_file, indent=2)
        if stats_path != get_conf_outstats().get("global"):
            return
        generate_stats_date(centres_stats)
        generate_stats_dep_date(centres_stats)
        generate_stats_center_types(centres_info)
        make_maps(centres_info)


def get_centres_info(center_data):
    with open(center_data, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    enable_logger_for_production()
    export_centres_stats()
