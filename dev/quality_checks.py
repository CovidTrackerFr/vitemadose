from typing import List, Optional
from dev.model import department

from dev.model.department import Center, Department

Departments = List[Department]


def _empty_or_null(string: Optional[str]) -> bool:
    return string is None or string == ""


def check_department_available_centers(department: Department) -> bool:
    return len(department.available_centers) > 0


department_checks = ((check_department_available_centers, "no available centers"),)


def check_center_no_empty_name(center: Center) -> bool:
    return not _empty_or_null(center.name)


def check_center_no_empty_url(center: Center):
    return not _empty_or_null(center.url)


def check_center_no_empty_location(center: Center):
    return (location := center.location) and location.latitude and location.longitude


def check_only_one_vaccine_type(center: Center):
    return center.vaccine_type and len(center.vaccine_type) == 1


center_checks = (
    (check_center_no_empty_name, "empty name"),
    (check_center_no_empty_url, "empty URL"),
    (check_center_no_empty_location, "empty or incomplete location"),
    (check_only_one_vaccine_type, "0 or more than one vaccine type"),
)


data = department.load_all()

for check, message in department_checks:
    failed = [department_id for department_id, department in data.items() if not check(department)]
    if failed:
        print(f"Departments with {message}")
        for department_id in failed:
            print(f" - {department_id}")

for check, message in center_checks:
    failed = [center for department in data.values() for center in department.available_centers if not check(center)]
    if failed:
        print(f"Centers with {message}")
        for center in failed:
            print(f" - [{center.department}] {center.name}")
