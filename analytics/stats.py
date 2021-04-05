import json
import os
from datetime import datetime

import pandas as pd

from scraper.departements import import_departements

OUTPUT_DATA_DIRPATH = 'data/output/'
OUTPUT_DATA_FILE = 'data/output/stats.json'


def get_all_data(codes=None):
    """
    Cette fonction peut prendre en parametre une liste de codes de departements (pour le debugging, essentiellement).
    Par defaut, renvoie la donnee de tous les departements.
    """
    codes = codes or import_departements()
    return pd.concat(get_formatted_departement_data(code) for code in codes)


def get_formatted_departement_data(departement_code):
    return _format_departement_data(_load_departement_data(departement_code))


def _load_departement_data(departement_code):
    path = os.path.join(OUTPUT_DATA_DIRPATH, f'{departement_code}.json')
    with open(path, 'r') as json_file:
        return json.load(json_file)


def _format_departement_data(json_data):
    available_centers = pd.json_normalize(json_data, 'centres_disponibles', ['last_updated'], record_prefix='')
    available_centers['status'] = 'disponible'
    unavailable_centers = pd.json_normalize(json_data, 'centres_indisponibles', ['last_updated'], record_prefix='')
    unavailable_centers['status'] = 'indisponible'
    return pd.concat([available_centers, unavailable_centers])


def _add_ratios(counts):
    """
    Ajoute quelques stats, telles que le nombre total de centres, ainsi que les proportions disponible/non-disponible.

    Attention: cette fonction modifie son premier argument.
    """
    counts['total'] = counts.disponible + counts.indisponible
    counts['ratio_disponible'] = counts.disponible / counts.total
    counts['ratio_indisponible'] = counts.indisponible / counts.total
    return counts


def export_results_to_json(national_stats, stats_by_departement):
    output_dict = {'computed_at': datetime.utcnow().isoformat(),
                   'stat_by_departement': stats_by_departement.to_dict(orient='index'),
                   'stat_nationale': national_stats.to_dict(orient='records')[0]}
    with open(OUTPUT_DATA_FILE, 'w') as output_json_file:
        json.dump(output_dict, output_json_file)


def main():
    all_centers = get_all_data()

    # Statistiques au niveau national
    national_stats = _add_ratios(all_centers.status.value_counts().to_frame().T)

    # Statistiques par departement
    stats_by_departement = (all_centers
                            .groupby(['departement', 'status'])
                            .size()
                            .unstack(fill_value=0))
    stats_by_departement = _add_ratios(stats_by_departement)

    export_results_to_json(national_stats, stats_by_departement)


if __name__ == '__main__':
    main()
