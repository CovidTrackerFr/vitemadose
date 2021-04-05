import datetime as dt
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def mock_datetime_now(now):
    class MockedDatetime(dt.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return now

    with patch("datetime.datetime", MockedDatetime):
        yield
