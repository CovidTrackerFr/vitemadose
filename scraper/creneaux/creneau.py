from dataclasses import dataclass
from enum import Enum
from pytz import timezone as Timezone
from datetime import datetime
from typing import Optional
from scraper.pattern.center_location import CenterLocation
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.vaccine import Vaccine


class Plateforme(str, Enum):
    DOCTOLIB = "Doctolib"
    MAIIA = "Maiia"
    ORDOCLIC = "Ordoclic"
    KELDOC = "Keldoc"
    MAPHARMA = "Mapharma"
    AVECMONDOC = "AvecMonDoc"


@dataclass
class Lieu:
    departement: str
    nom: str
    url: str
    lieu_type: str
    internal_id: str
    location: Optional[CenterLocation] = None
    metadata: Optional[dict] = None
    plateforme: Optional[Plateforme] = None


@dataclass
class Creneau:
    horaire: datetime
    lieu: Lieu
    reservation_url: str
    timezone: Timezone = Timezone("Europe/Paris")
    type_vaccin: Optional[Vaccine] = None
    disponible: bool = True


@dataclass
class PasDeCreneau:
    lieu: Lieu
    phone_only: bool = False
    disponible: bool = False
