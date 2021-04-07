import json
import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests

from utils.vmd_logger import enable_logger_for_production

logger = logging.getLogger('scraper')

DATA_AUTO = 'https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/'


def compute_plateforme_data(centres_info):
    plateformes = {}

    for dep in centres_info:
        dep_data = centres_info[dep]
        centers = dep_data.get('centres_disponibles', {})
        centers.extend(dep_data.get('centres_indisponibles', {}))
        for centre_dispo in centers:
            plateforme = centre_dispo['plateforme']
            if not plateforme:
                plateforme = 'Autre'
            next_app = centre_dispo.get('prochain_rdv', None)
            if plateforme not in plateformes:
                plateforme_data = {'disponible': 0, 'total': 0}
            else:
                plateforme_data = plateformes[plateforme]
            plateforme_data['disponible'] += 1 if next_app else 0
            plateforme_data['total'] += 1
            plateformes[plateforme] = plateforme_data
    return plateformes


def generate_stats_center_types(centres_info):
    stats_path = Path("data/output/stats_center_types.json")
    stats_data = {'dates': [], 'plateformes': {}}

    try:
        history_rq = requests.get(f"{DATA_AUTO}{stats_path}")
        data = history_rq.json()
        if data:
            stats_data = data
    except Exception as e:
        logger.warning(f"Unable to fetch {DATA_AUTO}{stats_path}: generating a template file.")
        pass
    ctz = pytz.timezone('Europe/Paris')
    current_time = datetime.now(tz=ctz).strftime("%Y-%m-%d %H:00:00")
    if current_time in stats_data['dates']:
        stats_path.write_text(json.dumps(stats_data))
        logger.info(f"Stats file already updated: {stats_path}")
        return

    stats_data['dates'].append(current_time)
    current_calc = compute_plateforme_data(centres_info)
    for plateforme in current_calc:
        plateform_data = current_calc[plateforme]
        if plateforme not in stats_data['plateformes']:
            stats_data['plateformes'][plateforme] = {
                'disponible': [plateform_data['disponible']],
                'total': [plateform_data['total']]
            }
            continue
        current_data = stats_data['plateformes'][plateforme]
        current_data['disponible'].append(plateform_data['disponible'])
        current_data['total'].append(plateform_data['total'])
    stats_path.write_text(json.dumps(stats_data))
    logger.info(f"Updated stats file: {stats_path}")
