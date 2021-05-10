import hashlib
from typing import Optional, List
from scraper.center_info import Vaccine


class ScraperRequest:
    def __init__(self, url: str, start_date: str):
        self.url: str = url
        self.start_date: str = start_date
        self.internal_id: Optional[str] = None
        self.practitioner_type: Optional[str] = None
        self.appointment_count: Optional[int] = 0
        self.appointment_schedules: Optional[List] = None
        self.vaccine_type: Optional[List[Vaccine]] = None
        self.appointment_by_phone_only: bool = False

    def update_internal_id(self, internal_id: Optional[str]) -> Optional[str]:
        self.internal_id = internal_id
        return self.internal_id

    def update_practitioner_type(self, practitioner_type: Optional[str]) -> Optional[str]:
        self.practitioner_type = practitioner_type
        return self.practitioner_type

    def update_appointment_count(self, appointment_count: Optional[int]) -> Optional[int]:
        self.appointment_count = appointment_count
        return self.appointment_count

    def update_appointment_schedules(self, appointment_schedules: Optional[list]):
        self.appointment_schedules = appointment_schedules

    def get_appointment_schedules(self) -> Optional[List]:
        return self.appointment_schedules

    def add_vaccine_type(self, vaccine_name: Optional[Vaccine]):
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

    def set_appointments_only_by_phone(self, only_by_phone: bool):
        self.appointment_by_phone_only = only_by_phone
