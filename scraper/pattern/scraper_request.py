class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url = url
        self.start_date = start_date

    def get_url(self) -> str:
        return self.url

    def get_start_date(self) -> str:
        return self.start_date
