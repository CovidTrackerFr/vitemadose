from enum import Enum
from typing import Optional, List, Dict


class Vaccine(str, Enum):
    PFIZER = "Pfizer-BioNTech"
    MODERNA = "Moderna"
    ASTRAZENECA = "AstraZeneca"
    JANSSEN = "Janssen"
    ARNM = "ARNm"


VACCINES_NAMES: Dict[Vaccine, List[str]] = {
    Vaccine.PFIZER: ["pfizer", "biontech"],
    Vaccine.MODERNA: ["moderna"],
    Vaccine.ARNM: ["arn", "arnm", "arn-m", "arn m"],
    Vaccine.ASTRAZENECA: ["astrazeneca", "astra-zeneca", "astra zeneca", "az"],  # Not too sure about the reliability
    Vaccine.JANSSEN: [
        "janssen",
        "jansen",
        "jansenn",
        "jannsen",
        "jenssen",
        "jensen",
        "jonson",
        "johnson",
        "johnnson",
        "j&j",
    ],
}


def get_vaccine_name(name: str, fallback: Optional[Vaccine] = None) -> Optional[Vaccine]:
    if not name:
        return fallback
    name = name.lower().strip()
    for vaccine in (Vaccine.ARNM, Vaccine.MODERNA, Vaccine.PFIZER, Vaccine.ASTRAZENECA, Vaccine.JANSSEN):
        vaccine_names = VACCINES_NAMES[vaccine]
        for vaccine_name in vaccine_names:
            if vaccine_name in name:
                if vaccine == Vaccine.ASTRAZENECA:
                    return get_vaccine_astrazeneca_minus_55_edgecase(name)
                return vaccine
    return fallback


def get_vaccine_astrazeneca_minus_55_edgecase(name: str) -> Vaccine:
    has_minus = "-" in name or "–" in name or "–" in name or "moins" in name
    if has_minus and "55" in name and "suite" in name:
        return Vaccine.ARNM
    return Vaccine.ASTRAZENECA
