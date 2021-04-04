from scraper.prototype import fetch_centre_slots


def test_fetch_centre_slots():
    """
    We detect which implementation to use based on the visit URL.
    """
    def fake_doctolib_fetch_slots(rdv_site_web, start_date):
        return "2021-04-04"

    def fake_keldoc_fetch_slots(rdv_site_web, start_date):
        return "2021-04-05"

    def fake_maiia_fetch_slots(rdv_site_web, start_date):
        return "2021-04-06"

    fetch_map = {
        "Doctolib": fake_doctolib_fetch_slots,
        "Keldoc": fake_keldoc_fetch_slots,
        "Maiia": fake_maiia_fetch_slots,
    }

    start_date = "2021-04-03"

    # Doctolib
    url = "https://partners.doctolib.fr/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Doctolib",
        "2021-04-04",
    )

    # Doctolib (old)
    url = "https://www.doctolib.fr/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Doctolib",
        "2021-04-04",
    )

    # Keldoc
    url = "https://vaccination-covid.keldoc.com/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Keldoc",
        "2021-04-05",
    )

    # Maiia
    url = "https://www.maiia.com/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Maiia",
        "2021-04-06",
    )

    # Default / unknown
    url = "https://www.example.com"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == ("Autre", None)
