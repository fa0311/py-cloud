from datetime import datetime
from typing import Union

import pytz


class RFC1123:
    def __init__(self, dt: datetime):
        self.dt = dt

    @classmethod
    def fromtimestamp(cls, timestamp: Union[int, float]) -> "RFC1123":
        return cls(datetime.fromtimestamp(timestamp))

    def rfc_1123(self) -> str:
        dt_utc = self.dt.astimezone(pytz.utc)
        return dt_utc.strftime("%a, %d %b %Y %H:%M:%S GMT")
