import click
import datetime as dt

from noaa_metrics.aggregate_logs import aggregate_logs
from noaa_metrics.ingest_logs import ingest_logs
from noaa_metrics.util.cli import DateType


@click.group()
def cli() -> None:
    pass


@cli.command(
    short_help="Ingest NOAA downloads log and write to JSON.",
)
@click.option(
    "-s",
    "--start_date",
    help="Start date (YYYY-MM-DD)",
    type=DateType(),
)
@click.option(
    "-e",
    "--end_date",
    help="End date (YYYY-MM-DD)",
    type=DateType(),
)
def ingest(start_date: dt.date, end_date: dt.date):
    """Ingest NOAA downloads log and write to JSON."""

    ingest_logs(start_date=start_date, end_date=end_date)


@cli.command(
    short_help="Generate NOAA downloads metric report.",
)
@click.option(
    "-s",
    "--start_date",
    help="Start date (YYYY-MM-DD)",
    type=DateType(),
)
@click.option(
    "-e",
    "--end_date",
    help="End date (YYYY-MM-DD)",
    type=DateType(),
)
@click.option("-m", "--mailto", help="Email(s) to send report to.", multiple=True)
@click.option(
    "-d",
    "--dataset",
    help="Select a specific dataset or 'all' (default).",
    default="all",
)
def report(start_date, end_date, mailto, dataset):
    """Generate NOAA downlaods metric report."""

    aggregate_logs(
        start_date=start_date, end_date=end_date, mailto=mailto, dataset=dataset
    )


if __name__ == "__main__":
    cli()
