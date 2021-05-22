from utils.vmd_geo_api import get_location_from_address, get_location_from_coordinates, Location, Coordinates

location: Location = {
    "full_address": "389 Av Mal de Lattre de Tassigny 71000 Mâcon",
    "number_street": "389 Av Mal de Lattre de Tassigny",
    "com_name": "Mâcon",
    "com_zipcode": "71000",
    "com_insee": "71270",
    "departement": "71",
    "longitude": 4.839588,
    "latitude": 46.315857,
}


def test_get_location_from_address():
    address: str = "389 Avenue Maréchal de Lattre de Tassigny"
    inseecode: str = "71270"  # Varennes-lès-Mâcon
    zipcode: str = "71000"

    assert get_location_from_address(address) != location
    assert get_location_from_address(address, zipcode=zipcode) == location
    assert get_location_from_address(address, inseecode=inseecode) == location


def test_get_location_from_coordinates():
    coordinates: Coordinates = Coordinates(4.8405438, 46.3165338)

    assert get_location_from_coordinates(coordinates) == location
