"""Dev helper file to explore `data/output/info_centres.json` and similar files.

Typically, you’d evaluate this file in a REPL, then: `data = load()` and start exploring.

Example: Figuring out if `vaccine_type` is always a list of one vaccine type:

    (Start a REPL and evaluate this file)
>>> from dev.model import department
>>> data = department.load_all()
>>> assert {
...     centre
...     for department_data in data.values()
...     for centre in department_data
...     if len(centre.vaccine_type) > 1
... }
True

"""
from __future__ import annotations

import json
from datetime import datetime
from itertools import chain
from pathlib import Path
from scraper.pattern.vaccine import Vaccine
from typing import Dict, Iterator, List, Optional

from pydantic import BaseModel, Field

from dev.model.schedule import Schedule


class Location(BaseModel):
    longitude: float
    latitude: float
    city: Optional[str]


class Center(BaseModel):
    department: str = Field(alias="departement")
    name: str = Field(alias="nom")
    url: str
    location: Optional[Location]
    metadata: dict
    next_appointment: Optional[datetime] = Field(alias="prochain_rdv")
    platform: str = Field(alias="plateforme")
    type: str
    appointment_count: int
    internal_id: Optional[str]
    vaccine_type: Optional[List[Vaccine]]
    appointment_by_phone_only: Optional[bool]
    error: Optional[str] = Field(alias="error")
    last_scan_with_availabilities: Optional[datetime]
    appointment_schedules: Optional[List[Schedule]]
    gid: str

    def __iter__(self) -> Iterator[Schedule]:
        return (self.appointment_schedules or []).__iter__()

    @property
    def is_available(self) -> bool:
        return self.appointment_schedules is not None


class Department(BaseModel):
    version: str
    last_updated: datetime
    available_centers: List[Center] = Field(alias="centres_disponibles")
    unavailable_centers: List[Center] = Field(alias="centres_indisponibles")

    def __iter__(self) -> Iterator[Center]:
        return chain(self.available_centers, self.unavailable_centers)

    @classmethod
    def load(cls, path: Path = Path("data", "output", "01.json")) -> Department:
        with open(path) as json_file:
            return cls(**json.load(json_file))


def load_all(path: Path = Path("data", "output", "info_centres.json")) -> Dict[str, Department]:
    with open(path) as json_file:
        return {department: Department(**data) for department, data in json.load(json_file).items()}
