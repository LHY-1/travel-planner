from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]
BROWSER_STATE_DIR = BASE_DIR / "browser_state"
PLAYWRIGHT_OUTPUT_DIR = BASE_DIR / "runtime_data"
PLAYWRIGHT_OUTPUT_DIR.mkdir(exist_ok=True)
BROWSER_STATE_DIR.mkdir(exist_ok=True)

TONGCHENG_STORAGE_STATE = os.getenv(
    "TONGCHENG_STORAGE_STATE",
    str(BROWSER_STATE_DIR / "tongcheng-storage.json"),
)
TONGCHENG_USE_BROWSER = os.getenv("TONGCHENG_USE_BROWSER", "1") == "1"
TONGCHENG_HEADLESS = os.getenv("TONGCHENG_HEADLESS", "0") == "1"
