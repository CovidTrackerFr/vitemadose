import json


class ScraperResult:
    def __init__(self, center_info, platform, next_availability):
        self.center_info = center_info
        self.platform = platform
        self.next_availability = next_availability

    def default(self):
        return self.__dict__
