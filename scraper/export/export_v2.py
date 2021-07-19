from utils.vmd_utils import q_iter
from scraper.creneaux.creneau import Creneau
from scraper.export.resource_centres import ResourceParDepartement, ResourceTousDepartements
from scraper.export.resource_creneaux_quotidiens import ResourceCreneauxQuotidiens
from scraper.pattern.tags import CURRENT_TAGS
import os
import json
import logging
from typing import Iterator
from dataclasses import dataclass
import sys


logger = logging.getLogger("scraper")


class JSONExporter:
    def __init__(self, departements=None, outpath_format="data/output/v2/{}.json"):
        self.outpath_format = outpath_format
        departements = departements if departements else Departement.all()
        resources_departements = {
            departement.code: ResourceParDepartement(departement.code) for departement in departements
        }
        resources_creneaux_quotidiens = {
            f"{departement.code}/creneaux-quotidiens": ResourceCreneauxQuotidiens(departement.code, tags=CURRENT_TAGS)
            for departement in departements
        }
        self.resources = {
            "info_centres": ResourceTousDepartements(),
            **resources_departements,
            **resources_creneaux_quotidiens,
        }

    def export(self, creneaux: Iterator[Creneau]):
        count = 0
        for creneau in creneaux:
            count += 1
            for resource in self.resources.values():
                resource.on_creneau(creneau)

        lieux_avec_creneau = len(self.resources["info_centres"].centres_disponibles)
        logger.info(f"Trouvé {count} créneaux dans {lieux_avec_creneau} lieux")
        for key, resource in self.resources.items():
            outfile_path = self.outpath_format.format(key)
            os.makedirs(os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                logger.debug(f"Writing file {outfile_path}")
                json.dump(resource.asdict(), outfile, indent=2)


@dataclass
class Departement:
    code_departement: str
    nom_departement: str
    code_region: int
    nom_region: str

    @property
    def code(self) -> str:
        return self.code_departement

    @property
    def nom(self) -> str:
        return self.nom_departement

    @classmethod
    def all(cls):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_source_path = os.path.join(dir_path, "../../data/output/departements.json")
        with open(json_source_path, "r") as source:
            departements = json.load(source)
        return [Departement(**dep) for dep in departements]
