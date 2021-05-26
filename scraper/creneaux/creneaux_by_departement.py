from datetime import datetime
import dateutil
from typing import Iterator


from scraper.creneaux.creneau import Creneau, Lieu, Plateforme

class CreneauxByDepartement:
    def __init__(self, departement, now=datetime.now):
        self.now = now
        self.departement = departement
        self.centres_disponibles = {}
        pass

    @classmethod
    def from_creneaux(cls, creneaux: Iterator[Creneau], departement, now=datetime.now):
        """
        On retourne un iterateur qui contient un seul et unique CreneauxByDepartement pour pouvoir découpler
        l'invocation de l'execution car l'execution ne se lance alors qu'à l'appel
        de `next(CreneauxByDepartement.from_creneaux())`
        """
        by_departement = CreneauxByDepartement(now=now, departement=departement)
        for creneau in creneaux:
            if creneau.lieu.departement == departement:
                by_departement.on_creneau(creneau)
        yield by_departement

    def on_creneau(self, creneau: Creneau):
        lieu = creneau.lieu
        if lieu.internal_id not in self.centres_disponibles:
            self.centres_disponibles[lieu.internal_id] = {
                    'internal_id': lieu.internal_id,
                    "departement": self.departement,
                    "nom": lieu.nom,
                    "url": lieu.url,
                    "location": {
                        'city': lieu.location.city,
                        'cp': lieu.location.cp,
                        'latitude': lieu.location.latitude,
                        'longitude': lieu.location.longitude
                    },
                    "metadata": lieu.metadata,
                    "prochain_rdv": None,
                    "plateforme": lieu.plateforme.value,
                    "type": lieu.type,
                    "appointment_count": 0,
                    "vaccine_type": [],
                    "appointment_by_phone_only": False,
                    "erreur": None,
                }
        centre = self.centres_disponibles[lieu.internal_id]
        centre['appointment_count'] += 1
        centre['vaccine_type'] = sorted(list(set(centre['vaccine_type'] + [creneau.type_vaccin.value])))
        if not centre['prochain_rdv'] or dateutil.parser.parse(centre['prochain_rdv']) > creneau.horaire:
            centre['prochain_rdv'] = creneau.horaire.strftime("%Y-%m-%dT%H:%M:%SZ")

    def asdict(self):
        return {
            'version': 1,
            'centres_disponibles': list(self.centres_disponibles.values()),
            'centres_indisponibles': [],
            'last_updated': self.now().isoformat()
        }
