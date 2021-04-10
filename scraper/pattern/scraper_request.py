class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url = url
        self.start_date = start_date
        self.internal_id = None
        self.practitioner_type = None
        self.appointment_count = 0

    def update_internal_id(self, internal_id):
        self.internal_id = internal_id

    def update_practitioner_type(self, practitioner_type):
        self.practitioner_type = practitioner_type

    def update_appointment_count(self, appointment_count):
        self.appointment_count = appointment_count

    def get_url(self) -> str:
        return self.url

    def get_start_date(self) -> str:
        return self.start_date
