# -- Tests de l'API (offline) --
import json
from pathlib import Path

import httpx

from scraper.keldoc.keldoc_center import KeldocCenter


def test_keldoc():
    center1_url = "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff?specialty=144"
    center1_redirect = "https://vaccination-covid.keldoc.com/redirect/?dom=centre-hospitalier-regional&inst=lorient-56100&user=groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff&specialty=144"

    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff":
            return httpx.Response(302, headers={
                "Location": center1_redirect
            })

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "next-slot-booking.json")
            return httpx.Response(200, json=json.loads(path.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(app))
    test_center_1 = KeldocCenter(base_url=center1_url, client=client)
    test_center_1.parse_resource()

def test_keldoc_motive_categories():
    pass

# -- Tests unitaires --


def test_keldoc_centers():
    pass
