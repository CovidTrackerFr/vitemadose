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
from utils.vmd_config import get_conf_outputs, get_config

logger = logging.getLogger("scraper")


class JSONExporter:
    def __init__(self, departements=None, outpath_format="data/output/{}.json"):
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

        lieux_avec_dispo = len(self.resources["info_centres"].centres_disponibles)
        lieux_sans_dispo = len(self.resources["info_centres"].centres_indisponibles)
        lieux_bloques_mais_dispo = len(self.resources["info_centres"].centres_bloques_mais_disponibles)

        if lieux_avec_dispo == 0:
            logger.error(
                "Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur"
            )
            exit(code=1)

        logger.info(
            f"{lieux_avec_dispo} centres ont des disponibilités sur {lieux_avec_dispo+lieux_sans_dispo} centre scannés (+{lieux_bloques_mais_dispo} bloqués)"
        )
        logger.info(f"{count} créneaux dans {lieux_avec_dispo} centres")
        print("\n")
        if lieux_bloques_mais_dispo > 0:
            logger.info(f"{lieux_bloques_mais_dispo} centres sont bloqués mais ont des disponibilités : ")
            for centre_bloque in self.resources["info_centres"].centres_bloques_mais_disponibles:
                logger.info(f"Le centre {centre_bloque} est bloqué mais a des disponibilités.")

        for key, resource in self.resources.items():
            outfile_path = self.outpath_format.format(key)
            os.makedirs(os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                logger.debug(f"Writing file {outfile_path}")
                json.dump(resource.asdict(), outfile, indent=2)

        with open(get_conf_outputs().get("data_gouv"), "w") as outfile:
            logger.debug(f'Writing file {get_conf_outputs().get("data_gouv")}')
            json.dump(self.resources["info_centres"].opendata, outfile, indent=2)


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
