from typing import TypedDict, Optional, NamedTuple
import requests
from utils.vmd_logger import get_logger

logger = get_logger()


class Location(TypedDict):
    full_address: str
    number_street: str
    com_name: str
    com_zipcode: str
    com_insee: str
    departement: str
    latitude: float
    longitude: float


class Coordinates(NamedTuple):
    longitude: float
    latitude: float


def get_location_from_address(
    address: str,
    zipcode: Optional[str] = None,
    inseecode: Optional[str] = None,
    coordinates: Optional[Coordinates] = None,
) -> Optional[Location]:
    params = {"q": address, "limit": 1}

    if zipcode:
        params["postcode"] = zipcode
    elif inseecode:
        params["citycode"] = inseecode
    elif coordinates:
        params["lat"] = getattr(coordinates, "latitude")
        params["lon"] = getattr(coordinates, "longitude")

    r = requests.get("https://api-adresse.data.gouv.fr/search/", params=params)

    return _parse_geojson(r.json())


def get_location_from_coordinates(coordinates: Coordinates) -> Optional[Location]:
    params = {"lon": getattr(coordinates, "longitude"), "lat": getattr(coordinates, "latitude")}

    r = requests.get("https://api-adresse.data.gouv.fr/reverse/", params=params)

    return _parse_geojson(r.json())


def _parse_geojson(geojson: str) -> Location:
    if not geojson["features"]:
        return None

    result = geojson["features"][0]
    prop = result["properties"]
    geometry = result["geometry"]

    if prop["type"] != "housenumber":
        logger.warning("GeoJSON imprecise, could not get a house number location.")

    return {
        "full_address": prop["label"],
        "number_street": prop["name"],
        "com_name": prop["city"],
        "com_zipcode": prop["postcode"],
        "com_insee": prop["citycode"],
        "departement": prop["context"].split(",")[0],
        "longitude": geometry["coordinates"][0],
        "latitude": geometry["coordinates"][1],
    }
