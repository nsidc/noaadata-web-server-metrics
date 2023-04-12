import datetime as dt
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
