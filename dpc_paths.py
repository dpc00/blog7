"""
Shared path constants for all DPC projects.
Requires DPC_ROOT environment variable pointing to the device root:
  Windows : C:\\Users\\donal
  WSL     : /home/dpchitester/sdcard
  Termux  : /sdcard
"""
import os
from pathlib import Path


def _require(var: str) -> Path:
    val = os.environ.get(var)
    if not val:
        raise RuntimeError(
            f"Environment variable {var!r} is not set. "
            "Set DPC_ROOT to your device root (e.g. C:\\Users\\donal or /sdcard)."
        )
    return Path(val)


ROOT     = _require("DPC_ROOT")
DATA     = ROOT / "data" / "finance"
DB_DIR   = DATA / "db"
SECRETS  = ROOT / "secrets" / "finance"
PROJECTS = ROOT / "projects"

FINANCE_DB = DB_DIR / "finance.db"
BLOG7_DB   = DB_DIR / "blog7.db"
NS_TOKEN   = SECRETS / "ns_token.txt"
NS_CREDS   = SECRETS / "ns_creds.txt"
