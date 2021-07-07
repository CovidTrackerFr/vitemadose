from typing import Dict, List

from pydantic import BaseModel


class CenterScraperConf(BaseModel):
    result_path: str = "data/output/doctolib-centers.json"
    business_days: List[str] = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    center_types: Dict[str, str] = {
        "pharmacie": "drugstore",
        "medecin": "general-practitioner",
        "*": "vaccination-center",
    }
    categories: List[str] = [
        "hopital-public",
        "centre-de-vaccinations-internationales",
        "centre-de-sante",
        "pharmacie",
        "medecin-generaliste",
        "centre-de-vaccinations-internationales",
        "centre-examens-de-sante",
    ]
    dep_conversion: Dict[str, str] = {
        "indre": "departement-indre",
        "gironde": "departement-gironde",
        "mayenne": "departement-mayenne",
        "vienne": "departement-vienne",
    }


class DoctolibConf(BaseModel):
    enabled: bool = True
    timeout: int = 30  # in seconds
    recognized_urls: List[str] = ["https://partners.doctolib.fr", "https://www.doctolib.fr"]
    build_url: str = "https://www.doctolib.fr{url_path}?pid={place_id}"
    api: Dict[str, str] = {
        "booking": "https://partners.doctolib.fr/booking/{centre}.json",
        "slots": "https://partners.doctolib.fr/availabilities.json?start_date={start_date}&visit_motive_ids={motive_id}&agenda_ids={agenda_ids_q}&insurance_sector=public&practice_ids={practice_ids_q}&destroy_temporary=true&limit={limit}",
        "scraper": "http://www.doctolib.fr/vaccination-covid-19/france.json?page={0}",
        "scraper_dep": "http://www.doctolib.fr/vaccination-covid-19/{0}.json?page={1}",
    }
    request_sleep: float = 0.1
    pagination: Dict[str, int] = {"pages": 4, "days": 7}
    filters: Dict[str, List[str]] = {
        "appointment_reason": [
            "1 ere injection",
            "1 ère injection",
            "1er injection",
            "1ere dose",
            "1ere injection",
            "1ère injection",
            "1re injection",
            "vaccination",
            "Vaccin COVID-19",
        ],
        "appointment_category": [
            "18 à 54",
            "55 ans",
            "70 ans",
            "50 ans",
            "18 ans",
            "16 ans",
            "astra Zeneca",
            "femmes enceintes",
            "grossesse",
            "injection unique",
            "janssen",
            "je ne suis pas professionnel de santé",
            "je suis un particulier",
            "non professionnels de santé",
            "patient",
            "personnes à très haut risque",
            "personnes âgées de 60 ans ou plus",
            "personnes de 60 ans et plus",
            "personnes de plus de",
            "pfizer",
            "public",
            "vaccination au centre",
            "vaccination covid",
            "vaccination pfizer",
            "assesseur",
            "vote",
        ],
    }
    center_scraper: CenterScraperConf = CenterScraperConf()
