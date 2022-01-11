from utils.vmd_geo_api import get_location_from_address, get_location_from_coordinates, Location, Coordinates

location1: Location = {
    "full_address": "389 Av Mal de Lattre de Tassigny 71000 Mâcon",
    "number_street": "389 Av Mal de Lattre de Tassigny",
    "com_name": "Mâcon",
    "com_zipcode": "71000",
    "com_insee": "71270",
    "departement": "71",
    "longitude": 4.839588,
    "latitude": 46.315857,
}


location2: Location = {
    "full_address": "4 Rue des Hibiscus 97200 Fort-de-France",
    "number_street": "4 Rue des Hibiscus",
    "com_name": "Fort-de-France",
    "com_zipcode": "97200",
    "com_insee": "97209",
    "departement": "972",
    "longitude": -61.078206,
    "latitude": 14.611228,
}


location3: Location = {
    "full_address": "Rue du Grand But (Lomme) 59000 Lille",
    "number_street": "Rue du Grand But (Lomme)",
    "com_name": "Lille",
    "com_zipcode": "59000",
    "com_insee": "59350",
    "departement": "59",
    "longitude": 2.975057,
    "latitude": 50.65017,
}


# This test actually calls to the API Adresse via Internet
# Slight updates in their result might break the assertion
# while not being an actual problem
# it's not that frequent

def test_get_location_from_address():
    # Common address
    address: str = "389 Avenue Maréchal de Lattre de Tassigny"
    inseecode: str = "71270"  # Varennes-lès-Mâcon
    zipcode: str = "71000"

    assert get_location_from_address(address) != location1  # Too generic, can't find with more input
    assert get_location_from_address(address, zipcode=zipcode) == location1
    assert get_location_from_address(address, inseecode=inseecode) == location1

    # Specific address, in DOM-TOM
    address: str = "4 rue des Hibiscus\n97200 Fort-de-France"
    assert get_location_from_address(address) == location2

    # Specific address with CEDEX code
    address: str = "Rue du Grand But - BP 249, 59462Cedex Lomme"
    cedexcode: str = "59462"
    inseecode: str = "59350"

    assert get_location_from_address(address) == location3
    assert get_location_from_address(address, zipcode=cedexcode) == None  # API Adresse does not handle CEDEX codes
    assert get_location_from_address(address, inseecode=inseecode) == location3

    # Check cache mechanism
    get_location_from_address.cache_clear()
    get_location_from_address(address)
    get_location_from_address(address)
    assert get_location_from_address.cache_info().hits == 1
    assert get_location_from_address.cache_info().misses == 1


def test_get_location_from_coordinates():
    coordinates: Coordinates = Coordinates(4.8405438, 46.3165338)

    assert get_location_from_coordinates(coordinates) == location1

    # Check cache mechanism
    get_location_from_coordinates.cache_clear()
    get_location_from_coordinates(coordinates)
    get_location_from_coordinates(coordinates)
    assert get_location_from_coordinates.cache_info().hits == 1
    assert get_location_from_coordinates.cache_info().misses == 1
