from datetime import datetime

from pydantic import BaseModel


class Schedule(BaseModel):
    name: str  # "chronodoses"
    from_: datetime  # "2021-05-10T00:00:00+02:00"
    to: datetime  # "2021-05-11T23:59:59+02:00"
    total: int

    def __init__(self, **kwargs):
        args = kwargs
        if "from" in args:
            args["from_"] = args.pop("from")
        super().__init__(**args)
