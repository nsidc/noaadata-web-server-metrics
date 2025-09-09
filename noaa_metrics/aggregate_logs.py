import calendar
import datetime as dt
import gc
import glob
import os
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.message import EmailMessage
from enum import Enum
from pathlib import Path
import multiprocessing as mp

import pandas as pd
import psutil

from noaa_metrics.constants.paths import (
    JSON_OUTPUT_DIR,
    REPORT_OUTPUT_DIR,
    REPORT_OUTPUT_FILEPATH,
)


def get_available_memory_gb():
    """Get available system memory in GB."""
    return psutil.virtual_memory().available / (1024**3)


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in MB."""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except:
        return 0


def read_json_file_safe(filepath: Path) -> pd.DataFrame:
    """Safely read a JSON file and return DataFrame."""
    try:
        if os.path.getsize(filepath) > 2:
            return pd.read_json(filepath)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return pd.DataFrame()


def create_dataframe_streaming_fallback(
    json_dir: Path, start_date: dt.date, end_date: dt.date
) -> pd.DataFrame:
    """
    Emergency fallback: ultra-conservative streaming approach.
    Processes one file at a time with aggressive memory management.
    """
    dates = pd.date_range(start_date, end_date, freq="d").tolist()
    filepaths = [
        json_dir / f"noaa-metrics-{date:%Y-%m-%d}.json" for date in dates
    ]
    
    print("Using emergency streaming mode...")
    
    # Start with empty DataFrame
    result_df = pd.DataFrame()
    total_rows = 0
    files_processed = 0
    
    for filepath in filepaths:
        if filepath.is_file() and os.path.getsize(filepath) > 2:
            size_mb = get_file_size_mb(filepath)
            available_gb = get_available_memory_gb()
            
            print(f"  {filepath.name} ({size_mb:.1f}MB, {available_gb:.1f}GB available)")
            
            # Skip files that are too large for current memory
            if size_mb > available_gb * 300:  # Conservative threshold
                print(f"    Skipping - file too large for available memory")
                continue
            
            try:
                df = pd.read_json(filepath)
                if not df.empty:
                    result_df = pd.concat([result_df, df], ignore_index=True)
                    total_rows += len(df)
                    files_processed += 1
                    print(f"    Added {len(df):,} rows (total: {total_rows:,})")
                    
                    # Periodic cleanup
                    if files_processed % 5 == 0:
                        gc.collect()
                        print(f"    Cleanup: {get_available_memory_gb():.1f}GB available")
                        
            except Exception as e:
                print(f"    Error: {e}")
                continue
    
    print(f"Streaming complete: {len(result_df):,} rows from {files_processed} files")
    return result_df


def create_dataframe(
    JSON_OUTPUT_DIR: Path, *, start_date: dt.date, end_date: dt.date
) -> pd.DataFrame:
    """
    Robust memory-aware approach for handling very large JSON files.
    Automatically adjusts strategy based on file sizes and available memory.
    """
    json_dir = Path(JSON_OUTPUT_DIR)
    
    dates = pd.date_range(start_date, end_date, freq="d").tolist()
    filepaths = [
        json_dir / f"noaa-metrics-{date:%Y-%m-%d}.json" for date in dates
    ]
    
    # Get existing files with sizes
    file_info = []
    total_size_mb = 0
    
    for filepath in filepaths:
        if filepath.is_file():
            size_mb = get_file_size_mb(filepath)
            if size_mb > 0:
                file_info.append((filepath, size_mb))
                total_size_mb += size_mb
    
    if not file_info:
        raise Exception("No valid files found")
    
    # Sort by size (largest first) for better memory management
    file_info.sort(key=lambda x: x[1], reverse=True)
    
    available_memory_gb = get_available_memory_gb()
    print(f"Found {len(file_info)} files, total size: {total_size_mb:.1f}MB")
    print(f"Available memory: {available_memory_gb:.1f}GB")
    
    # Categorize files by size
    HUGE_FILE_THRESHOLD = 50   # MB - process completely individually
    LARGE_FILE_THRESHOLD = 15  # MB - process in tiny batches
    
    huge_files = []
    large_files = []
    small_files = []
    
    for filepath, size_mb in file_info:
        if size_mb > HUGE_FILE_THRESHOLD:
            huge_files.append((filepath, size_mb))
        elif size_mb > LARGE_FILE_THRESHOLD:
            large_files.append((filepath, size_mb))
        else:
            small_files.append((filepath, size_mb))
    
    print(f"Strategy: {len(huge_files)} huge files (>{HUGE_FILE_THRESHOLD}MB), "
          f"{len(large_files)} large files ({LARGE_FILE_THRESHOLD}-{HUGE_FILE_THRESHOLD}MB), "
          f"{len(small_files)} small files (<{LARGE_FILE_THRESHOLD}MB)")
    
    all_dataframes = []
    
    # Process huge files one at a time with memory cleanup
    for filepath, size_mb in huge_files:
        print(f"Processing huge file: {filepath.name} ({size_mb:.1f}MB)")
        
        try:
            # Check available memory before loading
            available_gb = get_available_memory_gb()
            estimated_memory_need_gb = size_mb * 3 / 1024
            
            if available_gb < estimated_memory_need_gb:
                print(f"  Warning: Low memory ({available_gb:.1f}GB available, need ~{estimated_memory_need_gb:.1f}GB)")
                print("  Forcing garbage collection...")
                gc.collect()
            
            df = pd.read_json(filepath)
            if not df.empty:
                all_dataframes.append(df)
                print(f"  Loaded {len(df):,} rows, memory: {get_available_memory_gb():.1f}GB available")
            
        except MemoryError:
            print(f"  MEMORY ERROR: Skipping {filepath.name} - file too large for available memory")
            continue
        except Exception as e:
            print(f"  Error loading {filepath.name}: {e}")
            continue
    
    # Process large files in pairs
    if large_files:
        print(f"Processing {len(large_files)} large files in pairs...")
        
        for i in range(0, len(large_files), 2):
            batch = large_files[i:i+2]
            batch_files = [item[0] for item in batch]
            batch_sizes = [item[1] for item in batch]
            
            print(f"  Batch: {[f.name for f in batch_files]} ({sum(batch_sizes):.1f}MB total)")
            
            batch_dfs = []
            for filepath in batch_files:
                try:
                    df = pd.read_json(filepath)
                    if not df.empty:
                        batch_dfs.append(df)
                except Exception as e:
                    print(f"    Error: {e}")
            
            if batch_dfs:
                batch_combined = pd.concat(batch_dfs, ignore_index=True)
                all_dataframes.append(batch_combined)
                print(f"    Combined: {len(batch_combined):,} rows")
                
                # Cleanup batch DataFrames
                del batch_dfs, batch_combined
                gc.collect()
    
    # Process small files in larger batches
    if small_files:
        print(f"Processing {len(small_files)} small files in batches...")
        
        batch_size = 8
        small_file_paths = [item[0] for item in small_files]
        
        for i in range(0, len(small_file_paths), batch_size):
            batch_files = small_file_paths[i:i + batch_size]
            batch_dfs = []
            
            # Use threading for small files
            with ThreadPoolExecutor(max_workers=min(len(batch_files), 4)) as executor:
                future_to_file = {
                    executor.submit(read_json_file_safe, filepath): filepath 
                    for filepath in batch_files
                }
                
                for future in as_completed(future_to_file):
                    df = future.result()
                    if not df.empty:
                        batch_dfs.append(df)
            
            if batch_dfs:
                batch_combined = pd.concat(batch_dfs, ignore_index=True)
                all_dataframes.append(batch_combined)
                print(f"  Small batch {i//batch_size + 1}: {len(batch_combined):,} rows")
    
    # Final concatenation with memory monitoring
    if not all_dataframes:
        raise Exception("No data loaded successfully")
    
    print(f"Final concatenation of {len(all_dataframes)} DataFrames...")
    print(f"Memory before final concat: {get_available_memory_gb():.1f}GB available")
    
    try:
        log_df = pd.concat(all_dataframes, ignore_index=True)
        print(f"Success! Final DataFrame: {len(log_df):,} rows")
        print(f"Memory after concat: {get_available_memory_gb():.1f}GB available")
        
        # Cleanup intermediate DataFrames
        del all_dataframes
        gc.collect()
        
        return log_df
        
    except MemoryError:
        print("MEMORY ERROR in final concatenation!")
        print("Falling back to streaming approach...")
        return create_dataframe_streaming_fallback(json_dir, start_date, end_date)


def filter_by_dataset(log_df: pd.DataFrame, *, dataset: str) -> pd.DataFrame:
    """
    Select only specified dataset with validation.
    """
    available_datasets = log_df['dataset'].unique()
    if dataset not in available_datasets:
        print(f"Warning: Dataset '{dataset}' not found.")
        print(f"Available datasets: {', '.join(available_datasets)}")
        raise ValueError(f"Dataset '{dataset}' not found in data")
    
    filtered_df = log_df.loc[log_df["dataset"] == dataset]
    print(f"Filtered to {len(filtered_df):,} rows for dataset: {dataset}")
    return filtered_df


def get_summary_stats(log_df: pd.DataFrame) -> pd.DataFrame:
    """
    Collect stats for entire period.
    OPTIMIZED: Use vectorized operations instead of multiple agg calls.
    """
    unique_users = log_df["ip_address"].nunique()
    total_download_bytes = log_df["download_bytes"].sum()
    total_files = len(log_df)
    
    summary = {
        "Files Transmitted During Summary Period": total_files,
        "Volume in MB of files Transmitted During Summary Period": total_download_bytes,
        "Users Connecting During Summary Period": unique_users,
    }
    
    return pd.DataFrame.from_dict(summary, orient="index", columns=['Values'])


class AggregateBy(Enum):
    DATE = "date"
    DATASET = "dataset"
    TLD = "ip_location"


def downloads_by(
    log_df: pd.DataFrame, by: AggregateBy, *, column_header: str
) -> pd.DataFrame:
    """
    Group log_df by specified field.
    OPTIMIZED: Single groupby with dictionary aggregation for better performance.
    """
    agg_dict = {
        'ip_address': 'nunique',
        'file_path': 'count', 
        'download_bytes': 'sum'
    }
    
    aggregated_df = log_df.groupby(by.value).agg(agg_dict)
    
    # Rename columns
    aggregated_df.columns = [
        "Distinct Users",
        "Files Sent", 
        "Download Volume (MB)"
    ]
    
    # Format dates if needed
    if by == AggregateBy.DATE:
        aggregated_df.index = pd.to_datetime(aggregated_df.index).strftime("%d %b %Y")

    aggregated_df.index = aggregated_df.index.rename(column_header)
    aggregated_df.loc["Total"] = aggregated_df.sum()
    return aggregated_df


def df_to_csv(df: pd.DataFrame, *, header: str, output_csv: Path):
    """Write DataFrame to CSV with header."""
    with open(output_csv, "a") as file:
        file.write(header)
        df.to_csv(file, header=True, index=True)


def get_month_name(date: dt.date) -> str:
    """Return the name of the given date's month."""
    month = calendar.month_name[date.month]
    return month


def get_year(date: dt.date) -> int:
    """Return the year of the given date."""
    year = date.year
    return year


def send_mail(*, mailto: str, filename: str, subject: str, full_report: Path) -> None:
    """Send email with CSV report attachment."""
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
    """
    Aggregate log data for date period and dataset and send email report.
    Use robust memory-aware file reading for improved performance.
    """
    print(f"Date range: {start_date} to {end_date}")
    print(f"System memory: {get_available_memory_gb():.1f}GB available")
    print()
    
    print("Loading data with memory monitoring...")
    try:
        log_df = create_dataframe(JSON_OUTPUT_DIR, start_date=start_date, end_date=end_date)
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    print()
    
    if dataset != "all":
        log_df = filter_by_dataset(log_df, dataset=dataset)
    
    print("Generating reports...")
    
    start_month = get_month_name(start_date)
    end_month = get_month_name(end_date)
    start_year = get_year(start_date)
    end_year = get_year(end_date)
    
    summary_df = get_summary_stats(log_df)
    by_dataset_df = downloads_by(log_df, AggregateBy.DATASET, column_header="Dataset")
    by_day_df = downloads_by(log_df, AggregateBy.DATE, column_header="Date")
    by_location_df = downloads_by(log_df, AggregateBy.TLD, column_header="Domain")
    
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
            subject = f"NOAA Downloads {dataset} {start_month} {start_year} - {end_month} {end_year}"
            filename = f"NOAA-{dataset}-{start_month}-{start_year}-{end_month}-{end_year}.csv"
        else:
            summary_header = f"NOAA Downloads {start_month} - {end_month}\n\n"
            subject = f"NOAA Downloads {start_month} {start_year} - {end_month} {end_year}"
            filename = f"NOAA-{start_month}-{start_year}-{end_month}-{end_year}.csv"
    
    # Remove existing file so that it doesn't concatenate multiple times
    if os.path.exists(REPORT_OUTPUT_FILEPATH):
        os.remove(REPORT_OUTPUT_FILEPATH)

    print("Writing CSV report...")
    
    df_to_csv(
        summary_df, header=summary_header, output_csv=REPORT_OUTPUT_FILEPATH
    )
    df_to_csv(
        by_day_df, header="\nTransfers by Day\n\n", output_csv=REPORT_OUTPUT_FILEPATH
    )
    df_to_csv(
        by_dataset_df,
        header="\nTransfers by Dataset\n\n",
        output_csv=REPORT_OUTPUT_FILEPATH,
    )
    df_to_csv(
        by_location_df,
        header="\nTransfers by Domain\n\n",
        output_csv=REPORT_OUTPUT_FILEPATH,
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
    
    print("Email sent successfully!")
    print()
    print("=" * 60)
    print("AGGREGATION COMPLETE!")
    print("=" * 60)
    print(f"Final memory usage: {get_available_memory_gb():.1f}GB available")
