"""Application configuration for the Smart City Resource Intelligence demo."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_PATH = BASE_DIR / "data" / "sample_data.csv"
JSON_SORT_KEYS = False
