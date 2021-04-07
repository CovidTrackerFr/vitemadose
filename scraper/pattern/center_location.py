from typing import Optional


class CenterLocation:
    def __init__(self, longitude: float, latitude: float):
        self.longitude = longitude
        self.latitude = latitude

    def default(self):
        return self.__dict__


def convert_csv_data_to_location(csv_data: dict) -> Optional[CenterLocation]:
    long = csv_data.get('long_coor1', None)
    lat = csv_data.get('lat_coor1', None)

    if not long or not lat:
        return None
    return CenterLocation(long, lat)
