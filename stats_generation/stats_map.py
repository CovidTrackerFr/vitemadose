import io
import csv
import httpx
import logging

from datetime import date, datetime, timedelta
import pytz
from pathlib import Path

from utils.vmd_config import get_conf_inputs
from utils.vmd_logger import enable_logger_for_debug

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger("scraper")

PALETTE_FB = ["#ffffff", "#eaeaea", "#cecece", "#80bdf4", "#2d8dfe"]
PALETTE_FB_RDV = ["#eaeaea", "#F44848", "#FF9255", "#FFD84F", "#FEE487", "#7DF0AE", "#27DF76", "#00B94F"]
ECHELLE_STROKE = "#797979"
ECHELLE_FONT = "#424242"
MAP_SRC_PATH = Path(get_conf_inputs().get("map"))
CSV_POP_URL = get_conf_inputs().get("dep_pop")
CSV_RDV_URL = get_conf_inputs().get("rdv_gouv")
JSON_INFO_CENTRES_URL = get_conf_inputs().get("last_scans")


def get_csv(url: str, header=True, delimiter=";", encoding="utf-8", client: httpx.Client = DEFAULT_CLIENT):
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        return None

    reader = io.StringIO(r.content.decode(encoding))
    csvreader = csv.DictReader(reader, delimiter=delimiter)
    return csvreader


def get_json(url: str, client: httpx.Client = DEFAULT_CLIENT):
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        return None
    return r.json()


def make_svg(
    style: str, filename: str, echelle: list, echelle_labels: list = [], title: str = "vitemadose.covidtracker.fr"
):
    logger.info(f"making {filename}...")
    map_svg = ""
    paris_tz = pytz.timezone("Europe/Paris")
    with open(MAP_SRC_PATH, "r", encoding="utf-8") as f:
        map_svg = f.read()
    map_svg = map_svg.replace("/*@@@STYLETAG@@@*/", style)
    map_svg = map_svg.replace("@@@TITRETAG@@@", title)
    map_svg = map_svg.replace(
        "@@@UPDATETAG@@@", f'Dernière mise à jour: {datetime.now().astimezone(paris_tz).strftime("%d/%m/%Y %H:%M")}'
    )
    for i in range(0, 10):
        echelle_title = ""
        if i < len(echelle_labels):
            echelle_title = str(echelle_labels[i])
        map_svg = map_svg.replace(f"@e{i}", echelle_title)
    with open(Path("data", "output", filename), "w", encoding="utf-8") as f:
        f.write(map_svg)


def make_style(
    depts: dict,
    filename: str,
    palette: list,
    echelle: list,
    echelle_labels: list = [],
    title: str = "https://vitemadose.covidtracker.fr",
):
    style = ""
    if echelle_labels == []:
        echelle_labels = echelle
    for dept, dept_stat in depts.items():
        logger.debug(f"[{dept}] {dept_stat}")
        color = palette[len(palette) - 1]
        for i in range(0, len(echelle)):
            if dept_stat <= echelle[i]:
                color = palette[i]
                break
        dept_style = f".departement{dept.lower()} {{ fill: {color}; }}\n"
        style += dept_style

    style += f".echelle {{ stroke:{ECHELLE_STROKE}; stroke-width:0.5;}}\n"
    style += f".echelle-font {{ stroke:{ECHELLE_FONT}; }}\n"

    for i in range(0, 10):
        color = "none"
        stroke = "none"
        if i < len(palette):
            color = palette[i]
            stroke = ECHELLE_STROKE
        echelle_style = f".echelle{i} {{ fill: {color}; stroke: {stroke}; }}\n"
        style += echelle_style

    make_svg(style, filename, echelle, echelle_labels, title)


def make_stats_creneaux(stats):
    echelle = [0, 100, 500, 2000]
    labels = ["-", "100", "500", "2000", ">"]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        nb = min(dept_stat["creneaux"], ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(depts, "map_creneaux.svg", PALETTE_FB, echelle, echelle_labels=labels, title="Créneaux disponibles")


def make_stats_centres(stats: dict):
    echelle = [0, 5, 10, 20]
    labels = ["0", "5", "10", "20", ">"]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        nb = min(dept_stat["disponibles"], ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(
        depts,
        "map_centres.svg",
        PALETTE_FB,
        echelle,
        echelle_labels=labels,
        title="Centres ayant des créneaux disponibles",
    )


def make_stats_creneaux_pop(stats: dict):
    echelle = [0, 5, 10, 20]
    labels = ["0", "5", "10", "20", ">"]
    depts = {}
    ceiling = 1000000
    top_count = 0
    for dept, dept_stat in stats.items():
        if dept_stat["population"] == 0:
            logger.warning(f"No population data for department {dept}")
            continue
        nb = min(dept_stat["creneaux"] / (int(dept_stat["population"]) / 1000), ceiling)
        top_count = max(nb, top_count)
        depts[dept] = nb
    make_style(
        depts,
        "map_creneaux_pop.svg",
        PALETTE_FB,
        echelle,
        echelle_labels=labels,
        title="Créneaux disponibles pour 1000 habitants",
    )


def make_stats_rdv(dept_rdv: dict):
    echelle = [0, 40, 50, 60, 70, 80, 90]
    labels = ["-", "40%", "50%", "60%", "70%", "80%", "90%", ">"]
    depts = {}
    today = date.today()
    next_monday = (today + timedelta(days=7 - today.weekday())).strftime("%Y-%m-%d")
    previous_monday = (today + timedelta(days=0 - today.weekday())).strftime("%Y-%m-%d")
    logger.debug(f"next_monday: {next_monday}")
    logger.debug(f"previous_monday: {previous_monday}")
    monday = previous_monday
    for dept, dept_stat in dept_rdv.items():
        doses_allouees = 0
        rdv_pris = 0
        if monday not in dept_stat:
            continue
        doses_allouees += dept_stat[monday]["doses_allouees"]
        if doses_allouees == 0:
            logger.warning(f"No doses data for department {dept}")
            continue
        rdv_pris += dept_stat[monday]["rdv_pris"]
        taux = 100 * rdv_pris / doses_allouees
        depts[dept] = taux
    make_style(depts, "map_taux_rdv.svg", PALETTE_FB_RDV, echelle, echelle_labels=labels, title="rdv")


def make_maps(info_centres: dict):
    dept_pop = {}
    csv_pop = get_csv(CSV_POP_URL, header=True, delimiter=";")
    for row in csv_pop:
        dept_pop[row["dep"]] = row["departmentPopulation"]

    dept_rdv = {}
    csv_rdv = get_csv(CSV_RDV_URL, header=True, delimiter=",", encoding="windows-1252")

    for row in csv_rdv:
        date_debut_semaine = row["date_debut_semaine"]
        code_departement = row["code_departement"]
        doses_allouees = int(row["doses_allouees"])
        rdv_pris = int(row["rdv_pris"])
        if code_departement not in dept_rdv:
            dept_rdv[code_departement] = dict()
        if date_debut_semaine not in dept_rdv[code_departement]:
            dept_rdv[code_departement][date_debut_semaine] = {"doses_allouees": 0, "rdv_pris": 0}
        dept_rdv[code_departement][date_debut_semaine]["doses_allouees"] += doses_allouees
        dept_rdv[code_departement][date_debut_semaine]["rdv_pris"] += rdv_pris

    stats = {}

    for dept, info_centres_dept in info_centres.items():
        stats[dept] = {}
        centres_disponibles = 0
        centres_total = 0
        creneaux_disponibles = 0
        for centre_disponible in info_centres_dept.get("centres_disponibles", []):
            centres_disponibles += 1
            creneaux_disponibles += centre_disponible["appointment_count"]
        centres_total = centres_disponibles
        centres_total += len(info_centres_dept.get("centres_indisponibles", []))
        stats[dept] = {
            "disponibles": centres_disponibles,
            "total": centres_total,
            "creneaux": creneaux_disponibles,
            "population": dept_pop.get(dept, 0),
        }

    make_stats_creneaux(stats)
    make_stats_centres(stats)
    make_stats_creneaux_pop(stats)
    make_stats_rdv(dept_rdv)


def main():
    enable_logger_for_debug()
    info_centres = get_json(JSON_INFO_CENTRES_URL)
    make_maps(info_centres)


if __name__ == "__main__":
    main()
