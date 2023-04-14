import calendar
import datetime as dt
import glob
import os
import smtplib
from email.message import EmailMessage
from enum import Enum
from pathlib import Path

import pandas as pd

from noaa_metrics.constants.paths import (
    JSON_OUTPUT_DIR,
    REPORT_OUTPUT_DIR,
    REPORT_OUTPUT_FILEPATH,
)


def create_dataframe(
    JSON_OUTPUT_DIR: Path, *, start_date: dt.date, end_date: dt.date
) -> pd.DataFrame:
    """Create dataframe from JSON files."""
    dates = pd.date_range(start_date, end_date, freq="d").tolist()
    filepaths = [
        Path(JSON_OUTPUT_DIR / f"noaa-metrics-{date:%Y-%m-%d}.json") for date in dates
    ]
    expected_paths_nonexistent = [p for p in filepaths if not p.is_file()]
    if expected_paths_nonexistent:
        raise FileNotFoundError(
            f"Some expected paths don't exist: {expected_paths_nonexistent}"
        )

    dfs = []
    # TODO: figure out how to move on from the valueError on this step if there is no data for a day
    for f in filepaths:
        if os.path.getsize(f) > 2:
            data = pd.read_json(f)
            dfs.append(data)
        else:
            raise Exception(f"There were no downloads for {f}")
    log_df = pd.concat(dfs)
    return log_df


def filter_by_dataset(log_df: pd.DataFrame, *, dataset: str) -> pd.DataFrame:
    """Select only specified dataset."""
    filtered_df = log_df.loc[log_df["dataset"] == dataset]
    return filtered_df


def get_summary_stats(log_df: pd.DataFrame) -> pd.DataFrame:
    """Collect stats for entire period."""
    unique_users_df = log_df.agg({"ip_address": ["nunique"]})
    total_download_bytes_df = log_df.agg({"download_bytes": ["sum"]})
    total_files_df = log_df.agg({"file_path": ["count"]})
    unique_users = unique_users_df.iloc[0][0]
    total_download_bytes = total_download_bytes_df.iloc[0][0]
    total_files = total_files_df.iloc[0][0]
    summary = {
        "Files Transmitted During Summary Period": total_files,
        "Volume in MB of files Transmitted During Summary Period": total_download_bytes,
        "Users Connecting During Summary Period": unique_users,
    }
    summary_df1 = pd.DataFrame.from_dict(summary, orient="index")
    summary_df = summary_df1.rename(columns={0: "Values"})
    return summary_df


class AggregateBy(Enum):
    DATE = "date"
    DATASET = "dataset"
    TLD = "ip_location"


def downloads_by(
    log_df: pd.DataFrame, by: AggregateBy, *, column_header: str
) -> pd.DataFrame:
    """Group log_df by dataset.

    Count distinct users, sum total volume, and count number of files.
    """
    aggregated_df = log_df.groupby(by.value).agg(
        {"ip_address": ["nunique"], "file_path": ["count"], "download_bytes": ["sum"]}
    )
    aggregated_df.columns = aggregated_df.columns.droplevel(0)
    aggregated_df = aggregated_df.rename(
        columns={
            "nunique": "Distinct Users",
            "count": "Files Sent",
            "sum": "Download Volume (MB)",
        }
    )
    if by == AggregateBy.DATE:
        aggregated_df.index = pd.to_datetime(aggregated_df.index).strftime("%d %b %Y")

    aggregated_df.index = aggregated_df.index.rename(column_header)
    aggregated_df.loc["Total"] = aggregated_df.sum()
    return aggregated_df


def df_to_csv(df: pd.DataFrame, *, header: str, output_csv: Path):
    with open(output_csv, "a") as file:
        file.write(header)
        df.to_csv(file, header=True, index=True)


def get_month_name(date: dt.date) -> str:
    """Return the name of the given date's month."""
    month = calendar.month_name[date.month]
    return month


def get_year(date: dt.date) -> int:
    year = date.year
    return year


def send_mail(*, mailto: str, filename: str, subject: str, full_report: Path) -> None:
    msg = EmailMessage()
    msg["From"] = "archive@nusnow.colorado.edu"
    msg["To"] = mailto
    msg["Subject"] = subject

    with open(full_report) as fp:
        metrics_data = fp.read()
    msg.add_attachment(metrics_data, filename=filename)
    with smtplib.SMTP("localhost") as s:
        s.send_message(msg)


def aggregate_logs(
    *, start_date: dt.date, end_date: dt.date, mailto: str, dataset: str
) -> None:
    """Aggregate log data for date period and dataset and send email report."""
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    log_df = create_dataframe(JSON_OUTPUT_DIR, start_date=start_date, end_date=end_date)

    if dataset != "all":
        log_df = filter_by_dataset(log_df, dataset=dataset)

    start_month = get_month_name(start_date)
    end_month = get_month_name(end_date)
    year = get_year(start_date)
    summary_df = get_summary_stats(log_df)
    by_dataset_df = downloads_by(log_df, AggregateBy.DATASET, column_header="Dataset")
    by_day_df = downloads_by(log_df, AggregateBy.DATE, column_header="Date")
    by_location_df = downloads_by(log_df, AggregateBy.TLD, column_header="Domain")

    if start_month == end_month:
        # Show the dataset if we are filtering by one.
        if dataset != "all":
            summary_header = f"NOAA Downloads {dataset} {start_month}\n\n"
            subject = f"NOAA Downloads {dataset} {start_month} {year}"
            filename = f"NOAA-{dataset}-{start_month}-{year}.csv"
        else:
            summary_header = f"NOAA Downloads {start_month}\n\n"
            subject = f"NOAA Downloads {start_month} {year}"
            filename = f"NOAA-{start_month}-{year}.csv"
    # If there is more than one month encompassed then start and end month will be displayed.
    else:
        if dataset != "all":
            summary_header = f"NOAA Downloads {dataset} {start_month} - {end_month}\n\n"
            subject = f"NOAA Downloads {dataset} {start_month} - {end_month} {year}"
            filename = f"NOAA-{dataset}-{start_month}-{end_month}-{year}.csv"
        else:
            summary_header = f"NOAA Downloads {start_month} - {end_month}\n\n"
            subject = f"NOAA Downloads {start_month} - {end_month} {year}"
            filename = f"NOAA-{start_month}-{end_month}-{year}.csv"
    # remove existing file so that it doesn't concatenate multiple times
    if os.path.exists(REPORT_OUTPUT_FILEPATH):
        os.remove(REPORT_OUTPUT_FILEPATH)

    summary_csv = df_to_csv(
        summary_df, header=summary_header, output_csv=REPORT_OUTPUT_FILEPATH
    )
    by_day_csv = df_to_csv(
        by_day_df, header="\nTransfers by Day\n\n", output_csv=REPORT_OUTPUT_FILEPATH
    )
    by_dataset_csv = df_to_csv(
        by_dataset_df,
        header="\nTransfers by Dataset\n\n",
        output_csv=REPORT_OUTPUT_FILEPATH,
    )
    all_csv = df_to_csv(
        by_location_df,
        header="\nTransfers by Domain\n\n",
        output_csv=REPORT_OUTPUT_FILEPATH,
    )

    send_mail(
        mailto=mailto,
        filename=filename,
        subject=subject,
        full_report=REPORT_OUTPUT_FILEPATH,
    )
