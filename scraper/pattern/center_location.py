from typing import Optional

from utils.vmd_logger import get_logger

logger = get_logger()


class CenterLocation:
    def __init__(self, longitude: float, latitude: float):
        self.longitude = longitude
        self.latitude = latitude

    def default(self):
        return self.__dict__


def convert_csv_data_to_location(csv_data: dict) -> Optional[CenterLocation]:
    long = csv_data.get("long_coor1", None)
    lat = csv_data.get("lat_coor1", None)

    if not long or not lat:
        return None
    try:
        return CenterLocation(float(long), float(lat))
    except Exception as e:
        logger.error(f"Converting of csv to location failed : {e}")