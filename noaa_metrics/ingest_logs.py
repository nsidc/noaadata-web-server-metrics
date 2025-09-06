import datetime as dt
import json
import socket
from dataclasses import asdict
from pathlib import Path
from socket import gethostbyaddr
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Set

import pandas as pd

from noaa_metrics.constants.country_codes import COUNTRY_CODES
from noaa_metrics.constants.paths import JSON_OUTPUT_DIR, NGINX_DOWNLOAD_LOG_FILE
from noaa_metrics.util.dataclasses import ProcessedLogFields, RawLogFields
from noaa_metrics.util.json import DateFriendlyJSONEncoder


def log_line_in_date_range(log_line: str, start_date: dt.date, end_date: dt.date) -> bool:
    """
    date filtering - parse date directly from string without splits.
    Uses direct substring indexing for maximum performance.
    """
    try:
        date = dt.datetime.strptime(log_line[1:12], "%d/%b/%Y").date()
        return start_date <= date <= end_date
    except (ValueError, IndexError):
        return False

def get_log_lines() -> list[str]:
    """Get log entries as a list of strings.

    From /share/logs/noaa-web/download.log.
    """
    log_lines = []
    with open(NGINX_DOWNLOAD_LOG_FILE) as f:
        log_lines = [line.rstrip() for line in f]

    return log_lines



def line_to_raw_fields(log_line: str) -> RawLogFields:
    """ "Place the necessary info from the line into the dataclass."""
    split_line = log_line.split()
    log_fields = RawLogFields(
        date=dt.datetime.strptime(log_line[1:12], "%d/%b/%Y").date(),
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


@lru_cache(maxsize=10000)
def cached_ip_to_location(ip_address: str) -> str:
    """
    Cached DNS lookup - only does the lookup once per unique IP.
    """
    try:
        hostname = gethostbyaddr(ip_address)[0]
        host_suffix = hostname.split(".")[-1]
        if host_suffix not in COUNTRY_CODES:
            return COUNTRY_CODES[""]
        else:
            return COUNTRY_CODES[host_suffix]
    except socket.herror:
        return COUNTRY_CODES[""]


def batch_dns_lookups(ip_addresses: Set[str]) -> Dict[str, str]:
    """
    Perform DNS lookups for all unique IPs in parallel.
    This reduces DNS time from minutes to seconds.
    """
    def lookup_single_ip(ip: str) -> tuple[str, str]:
        location = cached_ip_to_location(ip)
        return ip, location
    
    ip_to_location = {}
    
    # Use 50 threads for I/O-bound DNS lookups
    with ThreadPoolExecutor(max_workers=50) as executor:
        # Submit all DNS lookup tasks
        future_to_ip = {executor.submit(lookup_single_ip, ip): ip for ip in ip_addresses}
        
        completed = 0
        for future in future_to_ip:
            ip, location = future.result()
            ip_to_location[ip] = location
            completed += 1
    
    return ip_to_location


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
        ip_location=cached_ip_to_location(log_fields_raw.ip_address)
    )
    return processed_log_fields


def process_raw_fields(
    log_dicts_raw: list[RawLogFields]) -> list[ProcessedLogFields]:
    """Enrich raw log data to include relevant information."""
    filtered_raw_fields = [
        log_fields_raw for log_fields_raw in log_dicts_raw
        if log_fields_raw.status.startswith("2")
        and not log_fields_raw.file_path.endswith("robots.txt")
    ]

    unique_ips = set(entry.ip_address for entry in filtered_raw_fields)

    # Batch DNS lookups (the magic happens here!)
    ip_to_location = batch_dns_lookups(unique_ips)

    log_dc = []

    for i, log_fields_raw in enumerate(filtered_raw_fields):
        processed_log_fields = ProcessedLogFields(
            date=log_fields_raw.date,
            ip_address=log_fields_raw.ip_address,
            download_bytes=log_fields_raw.download_bytes,
            dataset=get_dataset_from_path(log_fields_raw),
            file_path=log_fields_raw.file_path,
            ip_location=ip_to_location[log_fields_raw.ip_address],  # Use cached result - no DNS call!
        )
        log_dc.append(processed_log_fields)

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
    all_log_lines = get_log_lines()
    print(f"Total lines: {len(all_log_lines):,}")
    log_lines = [line for line in all_log_lines if log_line_in_date_range(line, start_date, end_date)]
    print(f"Filtered lines: {len(log_lines):,}")
    log_dicts_raw = lines_to_raw_fields(log_lines)
    log_dc = process_raw_fields(log_dicts_raw)

    log_dc_to_json_file(log_dc, start_date=start_date, end_date=end_date)
