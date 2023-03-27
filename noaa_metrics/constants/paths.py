from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent
PROJECT_DIR = PACKAGE_DIR.parent
JSON_OUTPUT_DIR = Path("/tmp")
JSON_OUTPUT_FILEPATH = JSON_OUTPUT_DIR / "test.json"
REPORT_OUTPUT_DIR = Path("/tmp")
REPORT_OUTPUT_FILEPATH = REPORT_OUTPUT_DIR / "noaa-downloads.csv"
CDR_REPORT_OUTPUT_FILEPATH = REPORT_OUTPUT_DIR / "noaa-cdr-march-2023.csv"
