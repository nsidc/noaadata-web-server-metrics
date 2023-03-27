import datetime as dt
import json
from dataclasses import dataclass


@dataclass
class RawLogFields:
    date: dt.date
    ip_address: str
    download_bytes: int
    file_path: str
    status: str


@dataclass
class ProcessedLogFields:
    date: dt.date
    ip_address: str
    download_bytes: int
    dataset: str
    file_path: str
    ip_location: str


@dataclass
class YearMonth:
    month: int
    year: int


class DateFriendlyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt.date):
            return obj.isoformat()
        return super(DateFriendlyJSONEncoder, self).default(obj)
