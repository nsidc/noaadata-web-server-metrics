import datetime as dt

import click
from click import Parameter, Context


class DateType(click.ParamType):
    name = "date"

    def __init__(self, formats=None) -> None:
        self.formats = formats or [
            "%Y-%m-%d",
            "%Y%m%d",
        ]

    def __repr__(self) -> str:
        return "Date"

    def get_metavar(self, param: Parameter, ctx: Context) -> str | None:
        formats_str = "|".join(self.formats)
        return f"[{formats_str}]"

    def convert(self, value, param, ctx):
        for fmt in self.formats:
            try:
                return dt.datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        self.fail(f"{value} is not a valid date. Expected one of: {self.formats}")
