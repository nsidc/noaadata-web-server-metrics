from pathlib import Path

# Where we get the logs
LOG_DIR = Path("/share/logs/noaa-web")
NGINX_DOWNLOAD_LOG_FILE = LOG_DIR / "download.log"

# Code locations
PACKAGE_DIR = Path(__file__).parent.parent
PROJECT_DIR = PACKAGE_DIR.parent

# Log output locations
JSON_OUTPUT_DIR = LOG_DIR / "ingest"
REPORT_OUTPUT_DIR = LOG_DIR / "report"
REPORT_OUTPUT_FILEPATH = REPORT_OUTPUT_DIR / "noaa-downloads.csv"
