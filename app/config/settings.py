from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

# 可选：从环境变量读取 token
TONGCHENG_TOKEN = os.getenv("TONGCHENG_TOKEN", "")
TONGCHENG_USER_ID = os.getenv("TONGCHENG_USER_ID", "0")
