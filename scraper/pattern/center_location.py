from typing import Optional

from utils.vmd_utils import departementUtils


class CenterLocation:
    def __init__(self, longitude: float, latitude: float, city: str):
        self.longitude = longitude
        self.latitude = latitude
        self.city = city

    def default(self):
        return self.__dict__


def convert_csv_data_to_location(csv_data: dict) -> Optional[CenterLocation]:
    long = csv_data.get('long_coor1', None)
    lat = csv_data.get('lat_coor1', None)
    city = csv_data.get('com_nom', None)

    if not long or not lat:
        return None
    if 'address' in csv_data:
        city = departementUtils.get_city(csv_data.get('address'))
    try:
        return CenterLocation(float(long), float(lat), city)
    except:
        return None
