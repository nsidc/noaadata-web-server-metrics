from setuptools import find_packages, setup

setup(
    name="noaadata-web-server-metrics",
    version="0.1.1",
    description="Generate email report of NSIDC NOAA https download metrics.",
    url="git@github.com:nsidc/noaadata-web-server-metrics.git",
    author="National Snow and Ice Data Center",
    author_email="nsidc@nsidc.org",
    packages=find_packages(),
    entry_points={"console_scripts": ["noaa_metrics = noaa_metrics.cli:cli"]},
    include_package_data=True,
)
