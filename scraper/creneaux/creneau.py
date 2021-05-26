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


class Lieu:
    def __init__(self,
                 departement: str,
                 nom: str,
                 url: str,
                 lieu_type: str,
                 internal_id: str,
                 location: Optional[CenterLocation] = None,
                 metadata: Optional[dict] = None,
                 plateforme: Optional[Plateforme] = None,
                 ):
        self.departement = departement
        self.internal_id = internal_id
        self.nom = nom
        self.url = url
        self.type = lieu_type
        self.location = location
        self.metadata = metadata
        self.plateforme = plateforme


class Creneau:
    def __init__(self,
                 horaire: datetime,
                 lieu: Lieu,
                 reservation_url: str,
                 timezone=Timezone("Europe/Paris"),
                 type_vaccin: Optional[Vaccine]=None,
                 ):
        self.horaire = horaire
        self.timezone = timezone
        self.type_vaccin = type_vaccin
        self.lieu = lieu
        self.timezone = timezone



