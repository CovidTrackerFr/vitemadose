from enum import Enum
from typing import Optional

from utils.vmd_config import get_config

VACCINE_CONF = get_config().get("vaccines", {})


class Vaccine(str, Enum):
    PFIZER = "Pfizer-BioNTech"
    MODERNA = "Moderna"
    ASTRAZENECA = "AstraZeneca"
    JANSSEN = "Janssen"
    ARNM = "ARNm"


VACCINES_NAMES = {
    Vaccine.PFIZER: VACCINE_CONF.get(Vaccine.PFIZER, []),
    Vaccine.MODERNA: VACCINE_CONF.get(Vaccine.MODERNA, []),
    Vaccine.ARNM: VACCINE_CONF.get(Vaccine.ARNM, []),
    Vaccine.ASTRAZENECA: VACCINE_CONF.get(Vaccine.ASTRAZENECA, []),
    Vaccine.JANSSEN: VACCINE_CONF.get(Vaccine.JANSSEN, []),
}


def get_vaccine_name(name: Optional[str], fallback: Optional[Vaccine] = None) -> Optional[Vaccine]:
    if not name:
        return fallback
    name = name.lower().strip()
    for vaccine, vaccine_names in VACCINES_NAMES.items():
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
