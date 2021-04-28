import io
import csv
import httpx
import logging

from pathlib import Path

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')

PALETTE_FB = ['#ffffff', '#eaeaea', '#cecece', '#80bdf4', '#2d8dfe']
ECHELLE_STROKE = '#797979'
ECHELLE_FONT = '#797979'
MAP_SRC_PATH = Path('data', 'input', 'map.svg')


def get_csv(url: str, header = True, delimiter = ';', client: httpx.Client = DEFAULT_CLIENT):
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f'{url} returned error {hex.response.status_code}')
        return None

    reader = io.StringIO(r.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=delimiter)
    result = {}
    for row in csvreader:
        result[row['dep']] = row['departmentPopulation']
    return result


def get_json(url: str, client: httpx.Client = DEFAULT_CLIENT):
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f'{url} returned error {hex.response.status_code}')
        return None
    return r.json()


def make_svg(style: str, filename: str, echelle: list, title: str = 'vitemadose.covidtracker.fr'):
    logger.info(f'making {filename}...')
    map_svg = ''
    with open(MAP_SRC_PATH, 'r', encoding='utf-8') as f:
        map_svg = f.read()
    map_svg = map_svg.replace('/*@@@STYLETAG@@@*/', style)
    map_svg = map_svg.replace('@@@TITRETAG@@@', title)
    for i in range(0, 10):
        echelle_title = ''
        if i < len(echelle):
            echelle_title = str(echelle[i])
        if i == len(echelle):
            echelle_title = '>'
        map_svg = map_svg.replace(f'@e{i}', echelle_title)
    with open(Path('data', 'output', filename), 'w', encoding='utf-8') as f:
        f.write(map_svg)


def make_style(depts: dict, filename: str, palette: list, echelle: list, 
               title: str = 'vitemadose.covidtracker.fr'):
    style = ''
    for dept, dept_stat in depts.items():
        color = palette[len(palette) - 1]
        for i in range(0, len(echelle)):
            if dept_stat <= echelle[i]:
                color = palette[i]
                break
        dept_style = f'.departement{dept.lower()} {{ fill: {color}; }}\n'
        style += dept_style

    style += f'.echelle {{ stroke:{ECHELLE_STROKE}; }}\n'
    style += f'.echelle-font {{ fill:{ECHELLE_FONT}; }}\n'

    for i in range(0, 10):
        color = '#ffffff'
        stroke = '#ffffff'
        if i < len(palette):
            color = palette[i]
            stroke = ECHELLE_STROKE
        echelle_style = f'.echelle{i} {{ fill: {color}; stroke: {stroke}; }}\n'
        style += echelle_style

    make_svg(style, filename, echelle, title)


def make_stats_creneaux(stats):
    echelle = [0, 100, 500, 2000]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        nb = min(dept_stat['creneaux'], ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(depts, 'map_creneaux.svg', PALETTE_FB, echelle, 'Créneaux disponibles')


def make_stats_centres(stats: dict):
    echelle = [0, 5, 10, 20]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        nb = min(dept_stat['disponibles'], ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(depts, 'map_centres.svg', PALETTE_FB, echelle, 
        'Centres ayant des créneaux disponibles')


def make_stats_creneaux_pop(stats: dict):
    echelle = [0, 5, 10, 20]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        nb = min(dept_stat['creneaux'] / (int(dept_stat['population']) / 1000), ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(depts, 'map_creneaux_pop.svg', PALETTE_FB, echelle, 
        'Créneaux disponibles pour 1000 habitants')

def make_maps(info_centres: dict):
    dept_pop = get_csv('https://raw.githubusercontent.com/rozierguillaume/covid-19/master/data/france/dep-pop.csv', 
                       header=True, delimiter=';')
    stats = {}

    for dept, info_centres_dept in info_centres.items():
        stats[dept] = {}
        centres_disponibles = 0
        centres_total = 0
        creneaux_disponibles = 0
        for centre_disponible in info_centres_dept.get('centres_disponibles', []):
            centres_disponibles += 1
            creneaux_disponibles += centre_disponible['appointment_count']
        centres_total = centres_disponibles
        centres_total += len(info_centres_dept.get('centres_indisponibles', []))
        stats[dept] = {'disponibles': centres_disponibles, 
                       'total': centres_total, 
                       'creneaux': creneaux_disponibles, 
                       'population': dept_pop.get(dept, 0)}
    
    make_stats_creneaux(stats)
    make_stats_centres(stats)
    make_stats_creneaux_pop(stats)


def main():
    info_centres = get_json('https://vitemadose.gitlab.io/vitemadose/info_centres.json')
    make_maps(info_centres)

if __name__ == "__main__":
    main()
