import sys

from invoke import task

from .util import PROJECT_DIR, print_and_run

sys.path.append(str(PROJECT_DIR))

from noaa_metrics.constants.paths import PACKAGE_DIR, PROJECT_DIR


@task(aliases=("mypy",))
def typecheck(ctx):
    """Check for type correctness using mypy."""
    print_and_run(f"mypy --config-file={PROJECT_DIR / '.mypy.ini'} {PACKAGE_DIR}/")
    print("🎉🦆 Type checking passed.")


@task(
    pre=[
        typecheck,
    ],
    default=True,
)
def all(ctx):
    """Run all of the tests."""
    print("🎉❤️  All tests passed!")
