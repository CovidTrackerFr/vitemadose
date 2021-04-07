import json
import logging
from datetime import datetime

import pytz
import requests

from stats_generation.stats_center_types import generate_stats_center_types
from utils.vmd_logger import enable_logger_for_production

logger = logging.getLogger('scraper')

STATS_BY_DATE = 'https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/data/output/stats_by_date.json'
STATS_BY_DATE_DEP = 'https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/data/output/stats_by_date_dep.json'


def generate_stats_date(centres_stats):
    stats_data = {'dates': [],
                  'total_centres_disponibles': [],
                  'total_centres': []
                  }

    try:
        history_rq = requests.get(STATS_BY_DATE)
        data = history_rq.json()
        if data:
            stats_data = data
    except Exception as e:
        logger.warning("Unable to fetch {0}: generating a template file.".format(STATS_BY_DATE))
        pass
    ctz = pytz.timezone('Europe/Paris')
    current_time = datetime.now(tz=ctz).strftime("%Y-%m-%d %H:00:00")
    if current_time in stats_data['dates']:
        logger.info("Stats file already updated: data/output/stats_by_date.json")
        return
    data_alldep = centres_stats['tout_departement']
    stats_data['dates'].append(current_time)
    stats_data['total_centres_disponibles'].append(data_alldep['disponibles'])
    stats_data['total_centres'].append(data_alldep['total'])

    with open("data/output/stats_by_date.json", "w") as stat_graph_file:
        json.dump(stats_data, stat_graph_file)
    logger.info("Updated stats file: data/output/stats_by_date.json")


def generate_stats_dep_date(centres_stats):
    stats_data = {'dates': [],
                  'dep_centres_disponibles': {},
                  'dep_centres': {}
                  }

    try:
        history_rq = requests.get(STATS_BY_DATE_DEP)
        data = history_rq.json()
        if data:
            stats_data = data
    except Exception as e:
        logger.warning("Unable to fetch {0}: generating a template file.".format(STATS_BY_DATE_DEP))
        pass
    ctz = pytz.timezone('Europe/Paris')
    current_time = datetime.now(tz=ctz).strftime("%Y-%m-%d %H:00:00")
    if current_time in stats_data['dates']:
        logger.info("Stats file already updated: data/output/stats_by_date_dep.json")
        return
    stats_data['dates'].append(current_time)

    for dep in centres_stats:
        if dep == 'tout_departement':
            continue
        if dep not in stats_data['dep_centres_disponibles']:
            stats_data['dep_centres_disponibles'][dep] = []
        if dep not in stats_data['dep_centres']:
            stats_data['dep_centres'][dep] = []
        dep_data = centres_stats[dep]
        stats_data['dep_centres_disponibles'][dep].append(dep_data['disponibles'])
        stats_data['dep_centres'][dep].append(dep_data['total'])

    with open("data/output/stats_by_date_dep.json", "w") as stat_graph_file:
        json.dump(stats_data, stat_graph_file)
    logger.info("Updated stats file: data/output/stats_by_date_dep.json")


def export_centres_stats(center_data='data/output/info_centres.json'):
    centres_info = get_centres_info(center_data)
    centres_stats = {
        "tout_departement": {
            "disponibles": 0,
            "total": 0,
        }
    }

    tout_dep_obj = centres_stats["tout_departement"]

    for dep_code, dep_value in centres_info.items():
        nombre_disponibles = len(dep_value["centres_disponibles"])
        count = len(dep_value["centres_indisponibles"]) + nombre_disponibles
        centres_stats[dep_code] = {
            "disponibles": nombre_disponibles,
            "total": count,
        }

        tout_dep_obj["disponibles"] += nombre_disponibles
        tout_dep_obj["total"] += count

    available_pct = (tout_dep_obj["disponibles"] / max(1, tout_dep_obj["total"])) * 100
    logger.info("Found {0}/{1} available centers. ({2}%)".format(tout_dep_obj["disponibles"],
                                                                 tout_dep_obj["total"], round(available_pct, 2)))
    with open("data/output/stats.json", "w") as stats_file:
        json.dump(centres_stats, stats_file, indent=2)
    generate_stats_date(centres_stats)
    generate_stats_dep_date(centres_stats)
    generate_stats_center_types(centres_info)


def get_centres_info(center_data):
    with open(center_data, "r") as f:
        return json.load(f)


if __name__ == '__main__':
    enable_logger_for_production()
    export_centres_stats()
