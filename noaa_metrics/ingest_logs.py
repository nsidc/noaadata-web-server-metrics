import datetime as dt
import json
import socket
from dataclasses import asdict
from pathlib import Path
from socket import gethostbyaddr

from noaa_metrics.constants.country_codes import COUNTRY_CODES
from noaa_metrics.constants.paths import JSON_OUTPUT_FILEPATH
from noaa_metrics.misc import DateFriendlyJSONEncoder, ProcessedLogFields, RawLogFields


def get_log_lines() -> list[str]:
    """Get log entries as a list of strings.

    From /share/logs/noaa-web/download.log.
    """
    log_file = Path("/share/logs/noaa-web-all/integration/download.log")
    log_lines = []
    with open(log_file) as file:
        log_lines = [line.rstrip() for line in file]

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
    breakpoint()
    return log_dicts_raw


def ip_address_to_ip_location(log_fields_raw: RawLogFields) -> str:
    """Take the ip address and use the country codes dictionary
    to match with the country/domain location"""
    ip = log_fields_raw.ip_address
    try:
        hostname = gethostbyaddr(ip)[0]
        host_suffix = hostname.split(".")[-1]
        ip_location = COUNTRY_CODES[host_suffix]
    except socket.herror:
        ip_location = COUNTRY_CODES[""]
    return ip_location


def get_dataset_from_path(log_fields_raw: RawLogFields) -> str:
    path = log_fields_raw.file_path
    if "NOAA" in path:
        noaa_dataset = path.split("NOAA/")[1]
        dataset = noaa_dataset.split("/")[0]
    elif "nsidc-0057" in path:
        dataset = "nsidc-0057"
    elif "nsidc-0008" in path:
        dataset = "nsidc-0008"
    elif "GPDP" in path:
        dataset = "GPDP"
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


def process_raw_fields(log_dicts_raw: list[RawLogFields]) -> list[ProcessedLogFields]:
    """Enrich raw log data to include relevant information."""
    log_dc = [
        raw_fields_to_processed_fields(log_fields_raw)
        for log_fields_raw in log_dicts_raw
        if log_fields_raw.status.startswith("2")
    ]
    return log_dc


def log_dc_to_json(log_dc: list[ProcessedLogFields]) -> str:
    """Create monthly log processed data file."""
    # TODO: This should take a month.
    log_dicts = [asdict(l) for l in log_dc]
    log_json = json.dumps(log_dicts, cls=DateFriendlyJSONEncoder)
    return log_json


def write_json_to_file(log_json: str) -> None:
    with open(JSON_OUTPUT_FILEPATH, "w") as f:
        f.write(log_json)


# Read in the log file
def main(start_date, end_date):
    log_lines = get_log_lines()
    log_dicts_raw = lines_to_raw_fields(log_lines)
    log_dc = process_raw_fields(log_dicts_raw)
    log_json = log_dc_to_json(log_dc)
    write_json_to_file(log_json)


if __name__ == "__main__":
    main()
