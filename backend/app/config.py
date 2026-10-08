"""Central configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

DATA_DIR = Path(os.environ.get("METRICA_DATA_DIR", ROOT_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
EXPERIMENT_DIR = DATA_DIR / "experiments"
DB_PATH = DATA_DIR / "metrica.db"

SAMPLE_DIR = ROOT_DIR / "sample_data"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

# Resource protection for a small instance (t3.micro: 2 vCPU, 1 GB RAM)
MAX_FILE_MB = int(os.environ.get("METRICA_MAX_FILE_MB", 50))
MAX_ROWS = int(os.environ.get("METRICA_MAX_ROWS", 100_000))
MAX_COLUMNS = int(os.environ.get("METRICA_MAX_COLUMNS", 200))
MAX_TRAIN_SECONDS = int(os.environ.get("METRICA_MAX_TRAIN_SECONDS", 120))

ALLOWED_EXTENSIONS = {".csv", ".txt", ".xls", ".xlsx"}
SESSION_DAYS = 7
COOKIE_NAME = "metrica_session"
# Set METRICA_COOKIE_SECURE=1 once the site is served over HTTPS.
COOKIE_SECURE = os.environ.get("METRICA_COOKIE_SECURE", "0") == "1"


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, EXPERIMENT_DIR):
        d.mkdir(parents=True, exist_ok=True)
