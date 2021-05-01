class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url = url
        self.start_date = start_date
        self.internal_id = None
        self.practitioner_type = None
        self.appointment_count = 0
        self.appointment_schedules = None
        self.vaccine_type = None
        self.appointment_by_phone_only = False

    def update_internal_id(self, internal_id):
        self.internal_id = internal_id

    def update_practitioner_type(self, practitioner_type):
        self.practitioner_type = practitioner_type

    def update_appointment_count(self, appointment_count):
        self.appointment_count = appointment_count

    def update_appointment_schedules(self, appointment_schedules : dict):
        self.appointment_schedules = appointment_schedules

    def get_appointment_schedules(self) -> list:
        return self.appointment_schedules

    def add_vaccine_type(self, vaccine_name):
        if not vaccine_name:
            return
        if self.vaccine_type is None:
            self.vaccine_type = []
        if vaccine_name in self.vaccine_type:
            return
        self.vaccine_type.append(vaccine_name)

    def get_url(self) -> str:
        return self.url

    def get_start_date(self) -> str:
        return self.start_date

    def set_appointments_only_by_phone(self, only_by_phone: bool) -> None:
        self.appointment_by_phone_only = only_by_phone
