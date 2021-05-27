from utils.vmd_utils import q_iter
from scraper.creneaux.creneau import Creneau
from scraper.creneaux.creneaux_by_departement import CreneauxByDepartement
import os
import json
import logging
from typing import Iterator
from dataclasses import dataclass

logger = logging.getLogger("scraper")

def export_by_departement(creneaux_it):
    count = 0
    lieux_vus = {}
    dep75 = CreneauxByDepartement('75')
    for creneau in creneaux_it:
        logger.debug(f"Got Creneau {creneau}")
        count += 1
        dep75.on_creneau(creneau)
        if creneau.lieu.internal_id in lieux_vus:
            lieux_vus[creneau.lieu.internal_id] += 1
        else:
            lieux_vus[creneau.lieu.internal_id] = 1
    logger.info(f"Trouvé {count} créneaux dans {len(lieux_vus)} lieux")
    print(json.dumps(lieux_vus, indent=2))
    print(json.dumps(dep75.asdict(), indent=2))

class JSONExporter:
    def __init__(self, departements=None, outpath_format="data/output/{}.json"):
        self.outpath_format = outpath_format
        departements = departements if departements else Departement.all()
        self.by_departement = {
            departement.code: CreneauxByDepartement(departement.code)
            for departement in departements
        }

    def export(self, creneaux: Iterator[Creneau]):
        count = 0
        for creneau in creneaux:
            logger.debug(f"Got Creneau {creneau}")
            count += 1
            for departement in self.by_departement.values():
                departement.on_creneau(creneau)

        lieux_avec_creneau = sum([len(departement.centres_disponibles) for departement in self.by_departement.values()])
        logger.info(f"Trouvé {count} créneaux dans {lieux_avec_creneau} lieux")
        for code, departement in self.by_departement.items():
            with open(self.outpath_format.format(code), 'w') as outfile:
                json.dump(departement.asdict(), outfile, indent=2)

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
        json_source_path = os.path.join(dir_path, '../../data/output/departements.json')
        with open(json_source_path, 'r') as source:
            departements = json.load(source)
        return [Departement(**dep) for dep in departements]

