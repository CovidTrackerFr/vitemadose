import json


class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url = url
        self.start_date = start_date

    def get_url(self) -> str:
        return self.url

    def get_start_date(self) -> str:
        return self.start_date


class CenterInfo:
    def __init__(self, request: ScraperRequest, service: str = 'Autre', phone_number: str = None, address: str = None):
        self.url = request.get_url(),
        self.service = service
        self.phone_number = phone_number
        self.address = address

    def default(self):
        return self.__dict__


class ScraperResult:
    def __init__(self, center_info, next_availability):
        self.center_info = center_info
        self.next_availability = next_availability

    def default(self):
        return self.__dict__
