"""Repository-relative path settings for the World Cup prediction lab."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_DIR.parent
PROJECT_DIR = SRC_DIR.parent

DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

REPORTS_DIR = PROJECT_DIR / "reports"
RUNS_DIR = PROJECT_DIR / "runs"
CONFIG_DIR = PROJECT_DIR / "config"

