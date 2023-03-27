FROM mambaorg/micromamba:1.4.0

WORKDIR /noaadata-web-server-metrics

# Activate the conda environment during build process
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# NOTE: For some reason, micromamba doesn't like the filename
# "environment-lock.yml". It fails to parse it because it's missing some
# special lockfile key.
COPY environment-lock.yml ./environment.yml

# Install dependencies to conda environment
RUN micromamba install -y \
    # NOTE: -p is important to install to the "base" env
    -p /opt/conda \
    -f environment.yml
RUN micromamba clean --all --yes

# Install source
COPY ./.mypy.ini .
COPY ./noaa_metrics ./noaa_metrics

ENV PYTHONPATH=/noaadata-web-server-metrics

# Test conda environment is correctly activated
RUN python noaa_metrics/cli.py --help

# Activate conda environment and run CLI as entrypoint
ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "python", "noaa_metrics/cli.py"]
