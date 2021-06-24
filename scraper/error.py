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


class DoublonDoctolib(ScrapeError):
    def __init__(self, url):
        super().__init__(
            "Doctolib", f"Le centre est un doublon ou ne propose pas de motif de vaccination sur ce lieu {url}"
        )
