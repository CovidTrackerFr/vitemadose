from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator, Union
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau


class Resource(ABC):
    @abstractmethod
    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):
        return None

    @abstractmethod
    def asdict(self):
        return {}

    @classmethod
    def from_creneaux(cls, creneaux: Iterator[Union[Creneau, PasDeCreneau]], *args, **kwargs):
        """
        On retourne un iterateur qui contient un seul et unique ResourceParDepartement pour pouvoir découpler
        l'invocation de l'execution car l'execution ne se lance alors qu'à l'appel
        de `next(ResourceParDepartement.from_creneaux())`
        """
        resource = cls(*args, **kwargs)
        for creneau in creneaux:
            resource.on_creneau(creneau)
        yield resource
