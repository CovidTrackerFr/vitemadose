from datetime import datetime
from scraper.pattern.vaccine import Vaccine
import dateutil
from dateutil.tz import gettz
from typing import Iterator, Union
from .resource import Resource
from utils.vmd_center_sort import sort_center

from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau


class ResourceTousDepartements(Resource):
    def __init__(self, now=datetime.now):
        self.now = now
        self.centres_disponibles = {}
        self.centres_indisponibles = {}

    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):
        lieu = creneau.lieu

        if isinstance(creneau, PasDeCreneau):
            self.centres_indisponibles[creneau.lieu.internal_id] = self.centre(lieu)
            return

        if lieu.internal_id not in self.centres_disponibles:
            self.centres_disponibles[lieu.internal_id] = self.centre(lieu)

        centre = self.centres_disponibles[lieu.internal_id]
        centre["appointment_count"] += 1

        if not centre["prochain_rdv"] or centre["prochain_rdv"] > creneau.horaire:
            centre["prochain_rdv"] = creneau.horaire

        if not creneau.type_vaccin:
            return

        for vaccine in creneau.type_vaccin:
            if not any([vaccine.value in one_vaccine for one_vaccine in centre["vaccine_type"]]):
                centre["vaccine_type"].append({vaccine.value: True})

    def centre(self, lieu: Lieu):
        return {
            "departement": lieu.departement,
            "nom": lieu.nom,
            "url": lieu.url,
            "location": self.location_to_dict(lieu.location),
            "metadata": lieu.metadata,
            "prochain_rdv": None,
            "plateforme": lieu.plateforme.value,
            "type": lieu.lieu_type,
            "appointment_count": 0,
            "internal_id": lieu.internal_id,
            "vaccine_type": [],
            "appointment_schedules": [],
            "appointment_by_phone_only": False,
            "erreur": None,
        }

    def location_to_dict(self, location):
        if not location:
            return None
        return {
            "longitude": location.longitude,
            "latitude": location.latitude,
            "city": location.city,
            "cp": location.cp,
        }

    def asdict(self):
        return {
            "version": 1,
            "last_updated": self.now(tz=gettz()).replace(microsecond=0).isoformat(),
            "centres_disponibles": sorted(
                [self.centre_asdict(c) for c in self.centres_disponibles.values()], key=sort_center
            ),
            "centres_indisponibles": [self.centre_asdict(c) for c in self.centres_indisponibles.values()],
        }

    def centre_asdict(self, centre):
        return {
            **centre,
            "prochain_rdv": centre["prochain_rdv"].replace(microsecond=0).isoformat()
            if centre["prochain_rdv"]
            else None,
            "vaccine_type": centre["vaccine_type"],
        }


class ResourceParDepartement(ResourceTousDepartements):
    def __init__(self, departement, now=datetime.now):
        super().__init__(now=now)
        self.departement = departement

    def on_creneau(self, creneau: Creneau):
        if creneau.lieu.departement == self.departement:
            return super().on_creneau(creneau)
