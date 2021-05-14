from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from pydantic.dataclasses import dataclass

from utils.vmd_utils import departementUtils
from utils.vmd_logger import get_logger

logger = get_logger()


@dataclass
class CenterLocation:
    longitude: float
    latitude: float
    city: Optional[str] = None
    cp: Optional[str] = None

    # TODO: Use `asdict()` directly, default is not clear.
    def default(self):
        return asdict(self)

    @classmethod
    def from_csv_data(cls, data: dict) -> Optional[CenterLocation]:
        long = data.get("long_coor1")
        lat = data.get("lat_coor1")
        city = data.get("com_nom")
        cp = data.get("com_cp")

        if long and lat:
            if address := data.get("address"):
                if not city:
                    city = departementUtils.get_city(address)
                if not cp:
                    cp = departementUtils.get_cp(address)
            try:
                return CenterLocation(long, lat, city, cp)
            except Exception as e:
                logger.warning("Failed to parse CenterLocation from {}".format(data))
                logger.warning(e)
        return


convert_csv_data_to_location = CenterLocation.from_csv_data
