from pathlib import Path

LOG_DIR = Path("/share/logs/noaa-web")
NGINX_DOWNLOAD_LOG_FILE = LOG_DIR / "download.log"

PACKAGE_DIR = Path(__file__).parent.parent
PROJECT_DIR = PACKAGE_DIR.parent

JSON_OUTPUT_DIR = Path("/tmp")
REPORT_OUTPUT_DIR = Path("/tmp")
REPORT_OUTPUT_FILEPATH = REPORT_OUTPUT_DIR / "noaa-downloads.csv"
