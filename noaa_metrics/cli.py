import datetime as dt

import click

from noaa_metrics.ingest_logs import ingest_logs
from noaa_metrics.aggregate_logs import aggregate_logs


class DateType(click.ParamType):
    name = "date"

    def __init__(self, formats=None):
        self.formats = formats or [
            "%Y-%m-%d",
            "%Y%m%d",
        ]

    def __repr__(self):
        return "Date"

    def get_metavar(self, param):
        formats_str = "|".join(self.formats)
        return f"[{formats_str}]"

    def convert(self, value, param, ctx):
        for fmt in self.formats:
            try:
                return dt.datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        self.fail(f"{value} is not a valid date. Expected one of: {self.formats}")


@click.group()
def cli():
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
def ingest(start_date, end_date):
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
    help="Select a specific dataset or all of them(default).",
    default="all",
)
def report(start_date, end_date, mailto, dataset):
    """Generate NOAA downlaods metric report."""

    aggregate_logs(start_date=start_date, end_date=end_date, mailto=mailto, dataset=dataset)


if __name__ == "__main__":
    cli()
