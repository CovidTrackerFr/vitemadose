from datetime import datetime
from scraper.pattern.center_info import CenterInfo
from scraper.pattern.vaccine import Vaccine
import dateutil
from dateutil.tz import gettz
from typing import Iterator, Union
from .resource import Resource
from utils.vmd_center_sort import sort_center
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
from utils.vmd_utils import departementUtils, is_reserved_center, get_config
from utils.vmd_blocklist import get_blocklist_urls, is_in_blocklist
import pytz
from scraper.creneaux.creneau import Plateforme

MAX_DOSE_IN_JSON=get_config().get("max_dose_in_classic_jsons")

blocklist = get_blocklist_urls()


class ResourceTousDepartements(Resource):
    def __init__(self, now=datetime.now):
        self.now = now
        self.centres_disponibles = {}
        self.centres_indisponibles = {}
        self.centres_bloques_mais_disponibles = {}
        self.opendata = []

    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):

        lieu = creneau.lieu
        centre = None
        is_blocked_center = lambda center: (is_reserved_center(center) or is_in_blocklist(center, blocklist))

        too_high_rank=False
        if creneau.dose:
            if creneau.dose>MAX_DOSE_IN_JSON:
                too_high_rank=True

        if not any(centre_opendata["url"] == lieu.url for centre_opendata in self.opendata):
            self.opendata.append(
                {"departement": lieu.departement, "plateforme": lieu.plateforme.value, "nom": lieu.nom, "url": lieu.url}
            )

        if not is_blocked_center(self.centre(lieu)):
            if isinstance(creneau, PasDeCreneau):
                self.centres_indisponibles[creneau.lieu.internal_id] = self.centre(lieu).default()
                return
            if too_high_rank:
                return
            if lieu.internal_id not in self.centres_disponibles:
                self.centres_disponibles[lieu.internal_id] = self.centre(lieu).default()
            
            centre = self.centres_disponibles[lieu.internal_id]
        else:
            self.centres_bloques_mais_disponibles[lieu.internal_id] = self.centre(lieu).default()

        if centre is not None and not too_high_rank:
            centre["appointment_count"] += 1

            if not centre["prochain_rdv"] or centre["prochain_rdv"] > creneau.horaire:
                centre["prochain_rdv"] = creneau.horaire

            if not creneau.type_vaccin:
                return

            if not isinstance(creneau.type_vaccin, list):
                creneau.type_vaccin = [creneau.type_vaccin]

            for vaccine in creneau.type_vaccin:
                if vaccine is not None:
                    if isinstance(vaccine, Vaccine):
                        vaccine = vaccine.value
                    if not any([vaccine in one_vaccine for one_vaccine in centre["vaccine_type"]]):
                        centre["vaccine_type"].append(vaccine)

    def centre(self, lieu: Lieu):
        return CenterInfo(
            departement=lieu.departement,
            nom=lieu.nom,
            url=lieu.url,
            location=self.location_to_dict(lieu.location),
            metadata=lieu.metadata,
            prochain_rdv=None,
            plateforme=lieu.plateforme.value,
            type=lieu.lieu_type,
            appointment_count=0,
            internal_id=lieu.internal_id,
            vaccine_type=[],
            erreur=None,
        )

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
            "last_updated": self.now(tz=pytz.timezone("Europe/Paris")).replace(microsecond=0).isoformat(),
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
