import calendar
import datetime as dt
import gc
import json
import os
import smtplib
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path

import psutil

from noaa_metrics.constants.paths import JSON_OUTPUT_DIR, REPORT_OUTPUT_FILEPATH

# Minimum bytes for a valid JSON file (empty array "[]")
MIN_VALID_JSON_FILE_SIZE = 2


def get_available_memory_gb() -> float:
    """Get available system memory in GB."""
    return psutil.virtual_memory().available / (1024**3)


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in MB."""
    return os.path.getsize(filepath) / (1024 * 1024)


class MetricsAccumulator:
    """
    Lightweight accumulator for metrics without using DataFrames.
    Processes data incrementally to avoid memory issues.
    """

    def __init__(self):
        # Summary stats
        self.total_files = 0
        self.total_download_bytes = 0
        self.unique_users = set()

        # Daily aggregations
        self.daily_stats = defaultdict(lambda: {"users": set(), "files": 0, "bytes": 0})

        # Dataset aggregations
        self.dataset_stats = defaultdict(
            lambda: {"users": set(), "files": 0, "bytes": 0}
        )

        # Location aggregations
        self.location_stats = defaultdict(
            lambda: {"users": set(), "files": 0, "bytes": 0}
        )

    def process_record(self, record):
        """Process a single log record."""
        # Extract fields (adjust field names to match your JSON structure)
        ip_address = record.get("ip_address", "")
        download_bytes = record.get("download_bytes", 0)
        date = record.get("date", "")
        dataset = record.get("dataset", "")
        ip_location = record.get("ip_location", "")

        # Summary stats
        self.total_files += 1
        self.total_download_bytes += download_bytes
        self.unique_users.add(ip_address)

        # Daily stats
        self.daily_stats[date]["users"].add(ip_address)
        self.daily_stats[date]["files"] += 1
        self.daily_stats[date]["bytes"] += download_bytes

        # Dataset stats
        self.dataset_stats[dataset]["users"].add(ip_address)
        self.dataset_stats[dataset]["files"] += 1
        self.dataset_stats[dataset]["bytes"] += download_bytes

        # Location stats
        self.location_stats[ip_location]["users"].add(ip_address)
        self.location_stats[ip_location]["files"] += 1
        self.location_stats[ip_location]["bytes"] += download_bytes

    def process_file_streaming(self, filepath: Path, max_chunk_size: int = 10000):
        """Process a JSON file in streaming fashion."""
        size_mb = get_file_size_mb(filepath)
        print(f"  Processing {filepath.name} ({size_mb:.1f}MB)")

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                # Process in chunks to avoid memory spikes
                total_records = len(data)
                processed = 0

                for i in range(0, total_records, max_chunk_size):
                    chunk = data[i : i + max_chunk_size]

                    for record in chunk:
                        self.process_record(record)
                        processed += 1

                    # Periodic cleanup and progress
                    if i % (max_chunk_size * 5) == 0:
                        gc.collect()
                        available_gb = get_available_memory_gb()
                        print(
                            f"Processed {processed:,}/{total_records:,} records,i"
                            f" {available_gb:.1f}GB available"
                        )

                        # Stop if memory getting too low
                        if available_gb < 1.0:
                            print(
                                f"Low memory - stopping processing of {filepath.name}"
                            )
                            break

                print(f"Completed: {processed:,} records from {filepath.name}")

                # Clean up the loaded data
                del data
                gc.collect()

                return processed
            else:
                # Single record
                self.process_record(data)
                return 1

        except Exception as e:
            print(f"    Error processing {filepath.name}: {e}")
            return 0

    def get_summary_stats(self):
        """Get summary statistics."""
        return {
            "Files Transmitted During Summary Period": self.total_files,
            (
                "Volume in MB of files Transmitted During Summary Period"
            ): self.total_download_bytes,
            "Users Connecting During Summary Period": len(self.unique_users),
        }

    def get_daily_stats(self):
        """Get daily aggregated statistics."""
        result = []
        total_users = set()
        total_files = 0
        total_bytes = 0

        # Sort dates
        sorted_dates = sorted(self.daily_stats.keys())

        for date in sorted_dates:
            stats = self.daily_stats[date]
            users_count = len(stats["users"])
            files_count = stats["files"]
            bytes_count = stats["bytes"]

            # Format date
            try:
                date_obj = dt.datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d %b %Y")
            except ValueError:
                formatted_date = date

            result.append(
                {
                    "Date": formatted_date,
                    "Distinct Users": users_count,
                    "Files Sent": files_count,
                    "Download Volume (MB)": bytes_count,
                }
            )

            # Track totals
            total_users.update(stats["users"])
            total_files += files_count
            total_bytes += bytes_count

        # Add total row
        result.append(
            {
                "Date": "Total",
                "Distinct Users": len(total_users),
                "Files Sent": total_files,
                "Download Volume (MB)": total_bytes,
            }
        )

        return result

    def get_dataset_stats(self):
        """Get dataset aggregated statistics."""
        result = []
        total_users = set()
        total_files = 0
        total_bytes = 0

        # Sort datasets
        sorted_datasets = sorted(self.dataset_stats.keys())

        for dataset in sorted_datasets:
            stats = self.dataset_stats[dataset]
            users_count = len(stats["users"])
            files_count = stats["files"]
            bytes_count = stats["bytes"]

            result.append(
                {
                    "Dataset": dataset,
                    "Distinct Users": users_count,
                    "Files Sent": files_count,
                    "Download Volume (MB)": bytes_count,
                }
            )

            # Track totals
            total_users.update(stats["users"])
            total_files += files_count
            total_bytes += bytes_count

        # Add total row
        result.append(
            {
                "Dataset": "Total",
                "Distinct Users": len(total_users),
                "Files Sent": total_files,
                "Download Volume (MB)": total_bytes,
            }
        )

        return result

    def get_location_stats(self):
        """Get location aggregated statistics."""
        result = []
        total_users = set()
        total_files = 0
        total_bytes = 0

        # Sort locations
        sorted_locations = sorted(self.location_stats.keys())

        for location in sorted_locations:
            stats = self.location_stats[location]
            users_count = len(stats["users"])
            files_count = stats["files"]
            bytes_count = stats["bytes"]

            result.append(
                {
                    "Domain": location,
                    "Distinct Users": users_count,
                    "Files Sent": files_count,
                    "Download Volume (MB)": bytes_count,
                }
            )

            # Track totals
            total_users.update(stats["users"])
            total_files += files_count
            total_bytes += bytes_count

        # Add total row
        result.append(
            {
                "Domain": "Total",
                "Distinct Users": len(total_users),
                "Files Sent": total_files,
                "Download Volume (MB)": total_bytes,
            }
        )

        return result


def write_dict_to_csv(data_dict, header, output_csv):
    """Write a dictionary to CSV with header."""
    with open(output_csv, "a") as file:
        file.write(header)
        for key, value in data_dict.items():
            file.write(f"{key},{value}\n")


def write_list_to_csv(data_list, header, output_csv):
    """Write a list of dictionaries to CSV with header."""
    if not data_list:
        return

    with open(output_csv, "a") as file:
        file.write(header)

        # Write column headers
        columns = list(data_list[0].keys())
        file.write(",".join(columns) + "\n")

        # Write data rows
        for row in data_list:
            values = [str(row.get(col, "")) for col in columns]
            file.write(",".join(values) + "\n")


def process_logs_lightweight(
    start_date: dt.date, end_date: dt.date, dataset: str = "all"
) -> MetricsAccumulator:
    """
    Process logs using lightweight approach without DataFrames.
    """
    json_dir = Path(JSON_OUTPUT_DIR)
    dates = [
        start_date + dt.timedelta(days=x)
        for x in range((end_date - start_date).days + 1)
    ]
    filepaths = [json_dir / f"noaa-metrics-{date:%Y-%m-%d}.json" for date in dates]

    print(f"Processing {len(dates)} days of data...")
    print(f"Available memory: {get_available_memory_gb():.1f}GB")

    # Get file info and sort by size (smallest first)
    file_info = []
    total_size_mb = 0

    for filepath in filepaths:
        if filepath.is_file() and os.path.getsize(filepath) > MIN_VALID_JSON_FILE_SIZE:
            size_mb = get_file_size_mb(filepath)
            file_info.append((filepath, size_mb))
            total_size_mb += size_mb

    file_info.sort(key=lambda x: x[1])  # Sort by size

    print(f"Found {len(file_info)} files, total size: {total_size_mb:.1f}MB")

    # Initialize accumulator
    accumulator = MetricsAccumulator()

    files_processed = 0
    total_records_processed = 0

    for filepath, size_mb in file_info:
        available_gb = get_available_memory_gb()

        # Skip files that are too large for current memory
        if size_mb > available_gb * 200 or available_gb < 1.5:
            print(
                f"Skipping {filepath.name} - too large ({size_mb:.1f}MB)"
                f" or low memory ({available_gb:.1f}GB)"
            )
            continue

        # Process the file
        records_processed = accumulator.process_file_streaming(filepath)

        if records_processed > 0:
            files_processed += 1
            total_records_processed += records_processed

            # Periodic memory cleanup
            if files_processed % 5 == 0:
                gc.collect()
                print(
                    f"Memory after {files_processed} files:"
                    f" {get_available_memory_gb():.1f}GB available"
                )

        # Stop if memory getting critically low
        if get_available_memory_gb() < 1.0:
            print("Critical memory level - stopping processing")
            break

    print(
        f"Processing complete: {total_records_processed:,}"
        f" records from {files_processed} files"
    )

    return accumulator


def get_month_name(date: dt.date) -> str:
    """Return the name of the given date's month."""
    return calendar.month_name[date.month]


def get_year(date: dt.date) -> int:
    """Return the year of the given date."""
    return date.year


def send_mail(*, mailto: str, filename: str, subject: str, full_report: Path) -> None:
    """Send email with CSV report attachment."""
    msg = EmailMessage()
    # msg["From"] = "archive@nusnow.colorado.edu"
    msg["From"] = "NOAA Archive <noreply@nsidc.org>"
    msg["To"] = mailto
    msg["Subject"] = subject

    # Add body text
    msg.set_content(
        "NOAA Download Metrics Report\n\n"
        "Please find the detailed CSV report attached.\n\n"
        "This is an automated report from the NOAA metrics system."
    )

    with open(full_report) as fp:
        metrics_data = fp.read()
    msg.add_attachment(metrics_data, filename=filename)
    with smtplib.SMTP("localhost") as s:
        s.send_message(msg)


def aggregate_logs(
    *, start_date: dt.date, end_date: dt.date, mailto: str, dataset: str
) -> None:
    """
    Lightweight version of aggregate_logs that avoids DataFrames entirely.
    """
    print(f"Date range: {start_date} to {end_date}")
    print(f"System memory: {get_available_memory_gb():.1f}GB available")
    print()

    print("Loading data with lightweight processing...")
    try:
        accumulator = process_logs_lightweight(start_date, end_date, dataset)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    print()
    print("Generating reports...")

    # Generate file naming
    start_month = get_month_name(start_date)
    end_month = get_month_name(end_date)
    start_year = get_year(start_date)
    end_year = get_year(end_date)

    # Get statistics
    summary_stats = accumulator.get_summary_stats()
    daily_stats = accumulator.get_daily_stats()
    dataset_stats = accumulator.get_dataset_stats()
    location_stats = accumulator.get_location_stats()

    print("Preparing output...")

    # Generate appropriate headers and filenames based on date range
    if start_month == end_month and start_year == end_year:
        # Single month
        if dataset != "all":
            summary_header = f"NOAA Downloads {dataset} {start_month}\n\n"
            subject = f"NOAA Downloads {dataset} {start_month} {start_year}"
            filename = f"NOAA-{dataset}-{start_month}-{start_year}.csv"
        else:
            summary_header = f"NOAA Downloads {start_month}\n\n"
            subject = f"NOAA Downloads {start_month} {start_year}"
            filename = f"NOAA-{start_month}-{start_year}.csv"
    else:
        # Multiple months
        if dataset != "all":
            summary_header = f"NOAA Downloads {dataset} {start_month} - {end_month}\n\n"
            subject = (
                f"NOAA Downloads {dataset} {start_month} {start_year} -"
                f"{end_month} {end_year}"
            )
            filename = (
                f"NOAA-{dataset}-{start_month}-{start_year}-{end_month}-{end_year}.csv"
            )
        else:
            summary_header = f"NOAA Downloads {start_month} - {end_month}\n\n"
            subject = (
                f"NOAA Downloads {start_month} {start_year} - {end_month} {end_year}"
            )
            filename = f"NOAA-{start_month}-{start_year}-{end_month}-{end_year}.csv"

    # Remove existing file
    if os.path.exists(REPORT_OUTPUT_FILEPATH):
        os.remove(REPORT_OUTPUT_FILEPATH)

    print("Writing CSV report...")

    # Write summary
    write_dict_to_csv(summary_stats, summary_header, REPORT_OUTPUT_FILEPATH)

    # Write daily stats
    write_list_to_csv(daily_stats, "\nTransfers by Day\n\n", REPORT_OUTPUT_FILEPATH)

    # Write dataset stats
    write_list_to_csv(
        dataset_stats, "\nTransfers by Dataset\n\n", REPORT_OUTPUT_FILEPATH
    )

    # Write location stats
    write_list_to_csv(
        location_stats, "\nTransfers by Domain\n\n", REPORT_OUTPUT_FILEPATH
    )

    print(f"CSV report written to: {REPORT_OUTPUT_FILEPATH}")
    print()

    print("Sending email...")
    send_mail(
        mailto=mailto,
        filename=filename,
        subject=subject,
        full_report=REPORT_OUTPUT_FILEPATH,
    )

    print(f"Final memory usage: {get_available_memory_gb():.1f}GB available")
