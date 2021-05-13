from datetime import datetime

from dev.model.schedule import Schedule


def test_initialization():
    schedule = Schedule(
        name="chronodose",
        from_="2021-05-10T00:00:00+02:00",
        to="2021-05-11T23:59:59+02:00",
        total=176,
    )

    assert schedule.name == "chronodose"
    assert isinstance(schedule.from_, datetime)
    assert isinstance(schedule.to, datetime)
    assert schedule.from_ <= schedule.to
    assert schedule.total == 176


def test_from_dict():
    data = {
        "name": "chronodose",
        "from": "2021-05-10T00:00:00+02:00",
        "to": "2021-05-10T00:00:00+02:00",
        "total": 176,
    }
    assert Schedule(**data) == Schedule(
        name="chronodose",
        from_="2021-05-10T00:00:00+02:00",
        to="2021-05-10T00:00:00+02:00",
        total=176,
    )
