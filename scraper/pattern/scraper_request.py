class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url = url
        self.start_date = start_date
        self.practitioner_type = None

    def update_practitioner_type(self, practitioner_type):
        self.practitioner_type = practitioner_type

    def get_url(self) -> str:
        return self.url

    def get_start_date(self) -> str:
        return self.start_date
