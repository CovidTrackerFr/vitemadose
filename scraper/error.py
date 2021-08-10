class ScrapeError(Exception):
    def __init__(self, plateforme="Autre", raison="Erreur de scrapping"):
        super().__init__(f"ERREUR DE SCRAPPING ({plateforme}): {raison}")
        self.plateforme = plateforme
        self.raison = raison


class BlockedByDoctolibError(ScrapeError):
    def __init__(self, url):
        super().__init__("Doctolib", f"Doctolib bloque nos appels: 403 {url}")


class BlockedByMesoignerError(ScrapeError):
    def __init__(self, url):
        super().__init__("Mesoigner", f"Mesoigner bloque nos appels: 403 {url}")


class BlockedByBimedocError(ScrapeError):
    def __init__(self, url):
        super().__init__("Bimedoc", f"Bimedoc bloque nos appels: 403 {url}")


class RequestError(ScrapeError):
    def __init__(self, url, response_code="wrong-url"):
        super().__init__("Doctolib", f"Erreur {response_code} lors de l'accès à {url}")
        self.blocked = True


class DoublonDoctolib(ScrapeError):
    def __init__(self, url):
        super().__init__(
            "Doctolib", f"Le centre est un doublon ou ne propose pas de motif de vaccination sur ce lieu {url}"
        )
