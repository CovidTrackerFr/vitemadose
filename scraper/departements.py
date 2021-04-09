import csv
import json
from typing import List


def import_departements() -> List[str]:
    """
    Renvoie la liste des codes départements.

    >>> departements = import_departements()
    >>> len(departements)
    101
    >>> departements[:3]
    ['01', '02', '03']
    >>> departements[83]
    '83'
    >>> departements.index('2A')
    28
    >>> sorted(departements) == departements
    True
    """
    with open("data/input/departements-france.csv", newline="\n") as csvfile:
        reader = csv.DictReader(csvfile)
        return [str(row["code_departement"]) for row in reader]


def to_departement_number(insee_code: str) -> str:
    """
    Renvoie le numéro de département correspondant au code INSEE d'une commune.

    Le code INSEE est un code à 5 chiffres, qui est typiquement différent du code postal,
    mais qui commence (en général) aussi par les 2 chiffres du département.

    >>> to_departement_number('59350')  # Lille
    '59'
    >>> to_departement_number('75106')  # Paris 6e arr
    '75'
    >>> to_departement_number('97701')  # Saint-Barthélémy
    '971'
    """
    if len(insee_code) == 4:
        # Quand le CSV des centres de vaccinations est édité avec un tableur comme Excel,
        # il est possible que le 1er zéro soit retiré si la colonne est interprétée comme
        # un nombre (par ex 02401 devient 2401, mais on veut 02401 au complet).
        insee_code = insee_code.zfill(5)

    if len(insee_code) != 5:
        raise ValueError(f'Code INSEE non-valide : {insee_code}')

    with open("data/input/insee_to_codepostal_and_code_departement.json") as json_file:
        insee_to_code_departement_table = json.load(json_file)

    if insee_code in insee_to_code_departement_table:
        return insee_to_code_departement_table[insee_code]["departement"]

    else:
        raise ValueError(f'Code INSEE absent de la base des codes INSEE : {insee_code}')