import datetime as dt
import json
import socket
from dataclasses import asdict
from pathlib import Path
from socket import gethostbyaddr

import pandas as pd

from noaa_metrics.constants.country_codes import COUNTRY_CODES
from noaa_metrics.constants.paths import JSON_OUTPUT_DIR, NGINX_DOWNLOAD_LOG_FILE
from noaa_metrics.util.dataclasses import ProcessedLogFields, RawLogFields
from noaa_metrics.util.json import DateFriendlyJSONEncoder


def get_log_lines() -> list[str]:
    """Get log entries as a list of strings.

    From /share/logs/noaa-web/download.log.
    """
    log_lines = []
    with open(NGINX_DOWNLOAD_LOG_FILE) as f:
        log_lines = [line.rstrip() for line in f]

    return log_lines


def date_from_split_line(split_line: list[str]) -> dt.date:
    """Convert the date from the log format '[17/Feb/2023:08:49:35'
    to date object with just Year, month, day."""
    datetime_string = split_line[0].strip("[")
    date_string = datetime_string.split(":")[0]
    date = dt.datetime.strptime(date_string, "%d/%b/%Y").date()
    return date


def line_to_raw_fields(log_line: str) -> RawLogFields:
    """ "Place the necessary info from the line into the dataclass."""
    split_line = log_line.split()
    log_fields = RawLogFields(
        date=date_from_split_line(split_line),
        ip_address=split_line[3],
        download_bytes=int(split_line[4]),
        file_path=split_line[5],
        status=split_line[6],
    )
    return log_fields


def lines_to_raw_fields(log_lines: list[str]) -> list[RawLogFields]:
    """Convert log lines into self describing data structures."""
    log_dicts_raw = [line_to_raw_fields(log_line) for log_line in log_lines]
    return log_dicts_raw


def ip_address_to_ip_location(log_fields_raw: RawLogFields) -> str:
    """Take the ip address and use the country codes dictionary
    to match with the country/domain location"""
    ip = log_fields_raw.ip_address
    try:
        hostname = gethostbyaddr(ip)[0]
        host_suffix = hostname.split(".")[-1]
        if not host_suffix in COUNTRY_CODES:
            # Add to unrecognized category if suffix isn't in list
            ip_location = COUNTRY_CODES[""]
        else:
            ip_location = COUNTRY_CODES[host_suffix]
    except socket.herror:
        ip_location = COUNTRY_CODES[""]
    return ip_location


def get_dataset_from_path(log_fields_raw: RawLogFields) -> str:

    path = log_fields_raw.file_path
    # NOTE: If a dataset that is not under 'NOAA/' is added, it must be added here too.
    if "NOAA/" in path:
        noaa_dataset = path.split("NOAA/")[1]
        dataset = noaa_dataset.split("/")[0]
    elif "nsidc-0057" in path:
        dataset = "nsidc-0057"
    elif "nsidc-0008" in path:
        dataset = "nsidc-0008"
    elif "GPDP" in path:
        dataset = "GPDP"
    else:
        raise RuntimeError(f'Could not determine dataset from {path=}.')
    return dataset


def raw_fields_to_processed_fields(log_fields_raw: RawLogFields) -> ProcessedLogFields:

    processed_log_fields = ProcessedLogFields(
        date=log_fields_raw.date,
        ip_address=log_fields_raw.ip_address,
        download_bytes=log_fields_raw.download_bytes,
        dataset=get_dataset_from_path(log_fields_raw),
        file_path=log_fields_raw.file_path,
        ip_location=ip_address_to_ip_location(log_fields_raw),
    )
    return processed_log_fields


def process_raw_fields(
    log_dicts_raw: list[RawLogFields], *, start_date: dt.date, end_date: dt.date
) -> list[ProcessedLogFields]:
    """Enrich raw log data to include relevant information."""
    log_dc = [
        raw_fields_to_processed_fields(log_fields_raw)
        for log_fields_raw in log_dicts_raw
        if log_fields_raw.status.startswith("2")
        and start_date <= log_fields_raw.date <= end_date
        and not log_fields_raw.file_path.endswith("robots.txt")
    ]
    return log_dc


def log_dc_to_json_file(
    log_dc: list[ProcessedLogFields], *, start_date: dt.date, end_date: dt.date
) -> None:
    """Create log processed data file."""
    dates = pd.date_range(start_date, end_date, freq="d").date.tolist()

    for d in dates:
        log_dict = [asdict(l) for l in log_dc if l.date == d]
        log_json = json.dumps(log_dict, cls=DateFriendlyJSONEncoder)
        write_json_to_file(log_json, date=d)


def write_json_to_file(log_json: str, *, date: dt.date) -> None:
    date_str = date.isoformat()
    JSON_OUTPUT_FILEPATH = JSON_OUTPUT_DIR / f"noaa-metrics-{date_str}.json"
    with open(JSON_OUTPUT_FILEPATH, "w") as f:
        f.write(log_json)


def ingest_logs(*, start_date: dt.date, end_date: dt.date) -> None:
    log_lines = get_log_lines()
    log_dicts_raw = lines_to_raw_fields(log_lines)
    log_dc = process_raw_fields(log_dicts_raw, start_date=start_date, end_date=end_date)

    log_dc_to_json_file(log_dc, start_date=start_date, end_date=end_date)
