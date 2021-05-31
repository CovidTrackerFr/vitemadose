from datetime import datetime
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
        centre['appointment_count'] += 1
        centre['vaccine_type'] = sorted(list(set(centre['vaccine_type'] + [creneau.type_vaccin.value])))
        if not centre['prochain_rdv'] or dateutil.parser.parse(centre['prochain_rdv']) > creneau.horaire:
            centre['prochain_rdv'] = creneau.horaire.replace(microsecond=0).isoformat()

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
            'internal_id': lieu.internal_id,
            "vaccine_type": [],
            "appointment_schedules": [],
            "appointment_by_phone_only": False,
            "erreur": None,
        }

    def location_to_dict(self, location):
        if not location:
            return None
        return {
            'longitude': location.longitude,
            'latitude': location.latitude,
            'city': location.city,
            'cp': location.cp,
        }

    def asdict(self):
        return {
            'version': 1,
            'last_updated': self.now(tz=gettz()).replace(microsecond=0).isoformat(),
            'centres_disponibles': sorted(list(self.centres_disponibles.values()), key=sort_center),
            'centres_indisponibles': list(self.centres_indisponibles.values()),
        }


class ResourceParDepartement(ResourceTousDepartements):
    def __init__(self, departement, now=datetime.now):
        super().__init__(now=now)
        self.departement = departement

    def on_creneau(self, creneau: Creneau):
        if creneau.lieu.departement == self.departement:
            return super().on_creneau(creneau)
