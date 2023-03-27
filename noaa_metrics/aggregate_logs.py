import calendar
import datetime as dt
import os
import smtplib
from email.message import EmailMessage

import pandas as pd

from constants.paths import (
    JSON_OUTPUT_FILEPATH,
    REPORT_OUTPUT_DIR,
    REPORT_OUTPUT_FILEPATH,
)


def create_dataframe(JSON_OUTPUT_FILEPATH) -> pd.DataFrame:
    """Create dataframe from JSON file."""
    all_log_df = pd.read_json(JSON_OUTPUT_FILEPATH)
    return all_log_df


def select_within_date_range(all_log_df: pd.DataFrame, start_date, end_date):
    """Reduce the dataframe to just the dates needed."""
    log_df = all_log_df.loc[all_log_df["date"].between(start_date, end_date)]
    return log_df


def get_period_summary_stats(log_df: pd.DataFrame):
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


def downloads_by_dataset(log_df: pd.DataFrame) -> pd.DataFrame:
    """Group log_df by dataset.

    Counting distinct users, summing total volume, couting number of files.
    """
    by_dataset_df = log_df.groupby("dataset").agg(
        {"ip_address": ["nunique"], "file_path": ["count"], "download_bytes": ["sum"]}
    )
    by_dataset_df.columns.set_levels(
        ["Distinct Users", "Files Sent", "Download Volume (MB)"], level=1, inplace=True
    )
    by_dataset_df.columns = by_dataset_df.columns.droplevel(0)
    by_dataset_df.index = by_dataset_df.index.rename("Dataset")
    by_dataset_df.loc["Total"] = by_dataset_df.sum()
    return by_dataset_df


def downloads_by_day(log_df: pd.DataFrame) -> pd.DataFrame:
    """Group log_df by date.

    Counting distinct users, summing total volume, couting number of files.
    """
    log_df["date"] = log_df["date"].dt.strftime("%d %b %Y")
    by_day_df = log_df.groupby("date").agg(
        {"ip_address": ["nunique"], "file_path": ["count"], "download_bytes": ["sum"]}
    )
    by_day_df.columns.set_levels(
        ["Distinct Users", "Files Sent", "Download Volume (MB)"], level=1, inplace=True
    )
    by_day_df.columns = by_day_df.columns.droplevel(0)
    by_day_df.index = by_day_df.index.rename("Date")
    by_day_df.loc["Total"] = by_day_df.sum()
    return by_day_df


def downloads_by_tld(log_df: pd.DataFrame) -> pd.DataFrame:
    """Group log_df by date.

    Counting distinct users, summing total volume, couting number of files.
    """
    ...
    by_location_df = log_df.groupby("ip_location").agg(
        {"ip_address": ["nunique"], "file_path": ["count"], "download_bytes": ["sum"]}
    )
    by_location_df.columns.set_levels(
        ["Distinct Users", "Files Sent", "Download Volume (MB)"], level=1, inplace=True
    )
    by_location_df.columns = by_location_df.columns.droplevel(0)
    by_location_df.index = by_location_df.index.rename("Domain Type")
    by_location_df.loc["Total"] = by_location_df.sum()
    return by_location_df


def df_to_csv(df: pd.DataFrame, header: str, output_csv):
    with open(output_csv, "a") as file:
        file.write(header)
        df.to_csv(file, header=True, index=True)


def get_month(date):
    date = dt.datetime.strptime(date, "%Y-%m-%d")
    month = calendar.month_name[(date.month)]
    return month


def get_year(date):
    date = dt.datetime.strptime(date, "%Y-%m-%d")
    year = date.year
    return year


def email_full_report(full_report, year, start_month, end_month, mailto: str):
    if start_month == end_month:
        subject = f"NOAA Downloads {start_month} {year}"
        filename = f"NOAA-{start_month}-{year}.csv"
    else:
        subject = f"NOAA Downloads {start_month} - {end_month} {year}"
        filename = f"NOAA-{start_month}-{end_month}-{year}.csv"
    msg = EmailMessage()
    msg["From"] = "archive@nusnow.colorado.edu"
    msg["To"] = mailto
    msg["Subject"] = subject

    with open(full_report) as fp:
        metrics_data = fp.read()
    msg.add_attachment(metrics_data, filename=filename)
    with smtplib.SMTP("localhost") as s:
        s.send_message(msg)


def main(start_date, end_date, mailto):

    all_log_df = create_dataframe(JSON_OUTPUT_FILEPATH)
    log_df = select_within_date_range(all_log_df, start_date, end_date)
    start_month = get_month(start_date)
    end_month = get_month(end_date)
    year = get_year(start_date)
    summary_df = get_period_summary_stats(log_df)
    by_dataset_df = downloads_by_dataset(log_df)
    by_day_df = downloads_by_day(log_df)
    by_location_df = downloads_by_tld(log_df)

    if start_month == end_month:
        summary_header = f"NOAA Downloads {start_month}\n\n"
    else:
        summary_header = f"NOAA Downloads {start_month} - {end_month}\n\n"

    # remove existing file so that it doesn't concatenate multiple times
    if os.path.exists(REPORT_OUTPUT_FILEPATH):
        os.remove(REPORT_OUTPUT_FILEPATH)

    summary_csv = df_to_csv(summary_df, summary_header, REPORT_OUTPUT_FILEPATH)
    by_day_csv = df_to_csv(by_day_df, "\nTransfers by Day\n\n", REPORT_OUTPUT_FILEPATH)
    by_dataset_csv = df_to_csv(
        by_dataset_df, "\nTransfers by Dataset\n\n", REPORT_OUTPUT_FILEPATH
    )
    all_csv = df_to_csv(
        by_location_df, "\nTransfers by Domain\n\n", REPORT_OUTPUT_FILEPATH
    )

    email_full_report(REPORT_OUTPUT_FILEPATH, year, start_month, end_month, mailto)


if __name__ == "__main__":
    main()
