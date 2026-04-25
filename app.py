"""
blog7 — Flask personal finance tracker for Termux/Android.

Run: python app.py
Open: http://localhost:5000
"""

import calendar
import math
import os
import re
import shutil
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import sqids as sqids_mod
from dateutil.relativedelta import relativedelta
from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "blog7-balance-log"


@app.context_processor
def _css_version():
    try:
        return {"css_v": int(Path(app.static_folder, "style.css").stat().st_mtime)}
    except OSError:
        return {"css_v": 0}


# ── Platform detection & data root ───────────────────────────────────────────

_ANDROID_ROOT = Path("/sdcard/data/finance")
_ANDROID_SECRETS_ROOT = Path("/sdcard/secrets/finance")
ANDROID = _ANDROID_ROOT.exists()
DATA_ROOT = _ANDROID_ROOT if ANDROID else Path.home() / "data" / "finance"
SECRETS_ROOT = (
    _ANDROID_SECRETS_ROOT if ANDROID else (Path.home() / "secrets" / "finance")
)

DB_PATH = DATA_ROOT / "db" / "blog7.db"
DB_BAK = DATA_ROOT / "db" / "blog7_backup.db"
SYNC_STATE_PATH = DATA_ROOT / "db" / "blog7.db.sync-state.json"
TOKEN_FILE = SECRETS_ROOT / "ns_token.txt"
CREDS_FILE = SECRETS_ROOT / "ns_creds.txt"
EBT_CREDS_FILE = SECRETS_ROOT / "ebt_creds.json"
RCLONE_CONF = SECRETS_ROOT / "rclone.conf"
SYNC_LOG = DATA_ROOT / "sync.log"

# ── NS API constants ──────────────────────────────────────────────────────────

_NS_BASE = "https://app.netspend.com"
_NS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-ns-client": (
        "app=spectrum; platform=web; brand=netspend; "
        "platformType=web; version=oac-v2.2.3; distributor=walgreens"
    ),
    "x-ns-variant": "variant://app.netspend.com",
    "Accept": "*/*",
    "Referer": "https://app.netspend.com/app/dashboard?drawer=transactions&isWW=true",
}
_NS_ASSET_ID = 2
_EBT_ASSET_ID = 3

_NS_LOGIN_URL = "https://www.netspend.com/profile-api/login"
_NS_LOGIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "X-NS-Client": (
        "app=Account Center; platform=web; platformType=web; "
        "brand=netspend; version=2026.14.0.1050"
    ),
    "X-NS-Variant": "variant://app.netspend.com",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.netspend.com",
    "Referer": "https://www.netspend.com/account/login",
}
_NS_DEVICE_FP = (
    "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;0400cPQTmysTpIrjK9GFecOQizm"
    "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"
)

# ── Utilities ─────────────────────────────────────────────────────────────────


def nc(d: float) -> float:
    return round(d * 100) / 100


def ncs(d: float) -> str:
    return f"{nc(d):,.2f}"


def dl(dom: int) -> float:
    """Days until next occurrence of day-of-month dom."""
    now = datetime.now()
    nd = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while True:
        days_in_month = calendar.monthrange(nd.year, nd.month)[1]
        actual_day = min(dom, days_in_month)
        nd = nd.replace(day=actual_day)
        if nd > now:
            break
        nd += relativedelta(months=1)
    return (nd - now).total_seconds() / 86400.0


def txtpa(txt: str) -> list:
    """Parse amount expression with optional flow-type suffix."""
    if not txt:
        return []
    pattern = re.compile(r"([+\-]?\s*[\d,]*\.?\d+)\s*(ex|in|ti|to|rr)?", re.IGNORECASE)
    results = []
    for m in pattern.finditer(txt):
        raw = m.group(1).replace(" ", "").replace(",", "")
        try:
            num = float(raw)
        except ValueError:
            continue
        if not math.isfinite(num):
            continue
        tag_raw = m.group(2)
        tag = tag_raw.lower() if tag_raw else ("in" if num >= 0 else "ex")
        results.append({"num": num, "tag": tag})
    return results


# ── DB ────────────────────────────────────────────────────────────────────────


class QueryResult:
    def __init__(self, data, fieldnames):
        self._data = data
        self._fieldnames = fieldnames

    def __getattr__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            try:
                return self._data[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    def __getitem__(self, key):
        try:
            return self._data[key]
        except KeyError:
            if isinstance(key, int):
                return self._data[self._fieldnames[key]]
            raise


def qr_factory(cursor, row):
    cds = [col[0] for col in cursor.description]
    data = {col: row[idx] for idx, col in enumerate(cds)}
    return QueryResult(data, cds)


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = qr_factory
        self._lock = threading.Lock()

    def execute(self, sql: str, params=()):
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def fetchall(self, sql: str, params=()):
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params=()):
        with self._lock:
            return self.conn.execute(sql, params).fetchone()

    def close(self):
        self.conn.close()

    def tblexists(self, nm: str) -> bool:
        row = self.fetchone(
            "SELECT COUNT() AS cnt FROM sqlite_master WHERE type='table' AND name=?",
            [nm],
        )
        return bool(row and row.cnt > 0)

    def init_schema(self):
        self.execute(
            """CREATE TABLE IF NOT EXISTS asset (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, type TEXT NOT NULL,
            current_balance REAL DEFAULT 0)"""
        )
        try:
            self.execute("ALTER TABLE asset ADD COLUMN current_balance REAL DEFAULT 0")
        except Exception:
            pass
        if self.fetchone("SELECT COUNT(*) AS c FROM asset").c == 0:
            for nm, tp in [
                ("Direct Express", "Prepaid Debit Card"),
                ("Netspend", "Prepaid Debit Card"),
                ("Colorado Quest", "EBT card"),
                ("Cash", "Wallet"),
            ]:
                self.execute("INSERT INTO asset (name,type) VALUES (?,?)", [nm, tp])

        self.execute(
            """CREATE TABLE IF NOT EXISTS source (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, type TEXT, day INTEGER, amount REAL, asset_id INTEGER)"""
        )
        if self.fetchone("SELECT COUNT(*) AS c FROM source").c == 0:
            for nm, tp, day, amt, aid in [
                ("SSA", "SSI", 26, 648, 2),
                ("CODHS", "OAP", 27, 189, 2),
                ("SSA", "Early Retirement", 31, 366, 2),
                ("CODHS", "FS", 8, 109, 3),
            ]:
                self.execute(
                    "INSERT INTO source (name,type,day,amount,asset_id) VALUES (?,?,?,?,?)",
                    [nm, tp, day, amt, aid],
                )

        self.execute(
            """CREATE TABLE IF NOT EXISTS nums (
            name TEXT PRIMARY KEY, num REAL, ts TIMESTAMP)"""
        )

        self.execute(
            """CREATE TABLE IF NOT EXISTS flow_types (
            flow INTEGER PRIMARY KEY, code TEXT NOT NULL,
            name TEXT, sign INTEGER NOT NULL DEFAULT 1)"""
        )
        if self.fetchone("SELECT COUNT(*) AS c FROM flow_types").c == 0:
            for flow, code, name, sign in [
                (1, "in", "income", 1),
                (2, "ex", "expense", -1),
                (3, "ti", "transfer_in", 1),
                (4, "to", "transfer_out", -1),
                (5, "rr", "refund_return", 1),
            ]:
                self.execute(
                    "INSERT INTO flow_types (flow,code,name,sign) VALUES (?,?,?,?)",
                    [flow, code, name, sign],
                )

        self.execute(
            """CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY, asset_id INTEGER NOT NULL,
            day DATE NOT NULL, amt REAL NOT NULL, flow INTEGER NOT NULL,
            balance REAL, desc TEXT)"""
        )
        for col, coltype in [
            ("income", "REAL"),
            ("expense", "REAL"),
            ("transfer_in", "REAL"),
            ("transfer_out", "REAL"),
            ("refund_return", "REAL"),
            ("ttype", "TEXT"),
            ("comp", "TEXT"),
            ("pprocs", "TEXT"),
            ("stnum", "TEXT"),
            ("amcode", "TEXT"),
            ("bwnum", "TEXT"),
            ("isite", "TEXT"),
            ("mcode", "TEXT"),
            ("address", "TEXT"),
            ("phone", "TEXT"),
        ]:
            try:
                self.execute(f"ALTER TABLE transactions ADD COLUMN {col} {coltype}")
            except Exception:
                pass

        for tbl in ("daily", "weekly", "monthly", "yearly"):
            info = {
                r[1]: r[5]
                for r in self.conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            }
            if info and ("f_in" in info or info.get("asset_id", 0) == 0):
                self.execute(f"DROP TABLE {tbl}")

        self.execute(
            """CREATE TABLE IF NOT EXISTS daily (
            day TEXT NOT NULL, asset_id INTEGER NOT NULL,
            income REAL, expense REAL, transfer_in REAL, transfer_out REAL, refund_return REAL,
            PRIMARY KEY (day, asset_id))"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS weekly (
            week TEXT NOT NULL, asset_id INTEGER NOT NULL,
            income REAL, expense REAL, transfer_in REAL, transfer_out REAL, refund_return REAL,
            PRIMARY KEY (week, asset_id))"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS monthly (
            month TEXT NOT NULL, asset_id INTEGER NOT NULL,
            income REAL, expense REAL, transfer_in REAL, transfer_out REAL, refund_return REAL,
            PRIMARY KEY (month, asset_id))"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS yearly (
            year TEXT NOT NULL, asset_id INTEGER NOT NULL,
            income REAL, expense REAL, transfer_in REAL, transfer_out REAL, refund_return REAL,
            PRIMARY KEY (year, asset_id))"""
        )

    def load_assets(self) -> list:
        rows = self.fetchall("SELECT * FROM asset ORDER BY asset_id")
        return [
            {
                "id": r.asset_id,
                "name": r.name,
                "ebt": 1 if r.type == "EBT card" else 0,
                "balance": r.current_balance or 0.0,
            }
            for r in rows
        ]

    def save_asset_balance(self, asset_id: int, balance: float):
        self.execute(
            "UPDATE asset SET current_balance=? WHERE asset_id=?", [balance, asset_id]
        )

    def load_number(self, name: str) -> float:
        row = self.fetchone("SELECT num FROM nums WHERE name=?", [name])
        return row.num if row else 0.0

    def save_number(self, name: str, num: float):
        self.execute(
            "INSERT OR REPLACE INTO nums (name,num,ts) VALUES (?,?,?)",
            [name, num, datetime.now().isoformat()],
        )

    def log_txn(self, asset_id: int, amt: float, balance: float, flow_code: str):
        row = self.fetchone("SELECT flow FROM flow_types WHERE code=?", [flow_code])
        flow = row.flow if row else 2
        txn_id = f"{asset_id}_{datetime.now().isoformat()}"
        self.execute(
            "INSERT OR IGNORE INTO transactions (id, asset_id, day, amt, flow, balance, desc)"
            " VALUES (?,?,?,?,?,?,?)",
            [
                txn_id,
                asset_id,
                datetime.now().strftime("%Y-%m-%d"),
                amt,
                flow,
                balance,
                None,
            ],
        )

    def load_sources(self, excl_asset_ids: list) -> list:
        if excl_asset_ids:
            ph = ",".join("?" * len(excl_asset_ids))
            rows = self.fetchall(
                f"SELECT * FROM source WHERE asset_id NOT IN ({ph}) ORDER BY source_id",
                excl_asset_ids,
            )
        else:
            rows = self.fetchall("SELECT * FROM source ORDER BY source_id")
        return [
            {
                "id": r.source_id,
                "name": r.name,
                "type": r.type,
                "day": r.day,
                "amount": r.amount,
            }
            for r in rows
        ]


db = DB(DB_PATH)
db.init_schema()

# ── Google Drive sync ─────────────────────────────────────────────────────────

GD_FILENAME = "blog7.db"

# ── Sync-state sidecar ───────────────────────────────────────────────────────

SYNC_STATE_VERSION = 1


def _read_sync_state(path):
    """Return parsed dict or None if missing/unreadable."""
    import json

    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def _write_sync_state(path, revision_id, gd_modified_time, local_mtime, device):
    """Atomic-ish write of sync-state sidecar."""
    import json

    payload = {
        "version": SYNC_STATE_VERSION,
        "revision_id": revision_id,
        "gd_modified_time": gd_modified_time.isoformat(),
        "local_mtime": local_mtime,
        "device": device,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _device_id():
    return "phone" if ANDROID else "laptop"


def _sync_log(msg):
    try:
        with open(str(SYNC_LOG), "a") as f:
            f.write(f"{datetime.now()}: {msg}\n")
    except Exception:
        pass


GD_DB_REMOTE = "GD:data/finance/db/blog7.db"


def _rclone_base_cmd():
    cmd = ["rclone"]
    if RCLONE_CONF.exists():
        cmd += ["--config", str(RCLONE_CONF)]
    return cmd


def _rclone_drive_remote():
    import configparser

    if RCLONE_CONF.exists():
        cp = configparser.ConfigParser()
        cp.read(str(RCLONE_CONF))
        for section in cp.sections():
            if cp.get(section, "type", fallback="") == "drive":
                return section
    return "GD"


def _gd_db_remote():
    return f"{_rclone_drive_remote()}:data/finance/db/{GD_FILENAME}"


def _rclone_run(args, timeout=60):
    return subprocess.run(
        _rclone_base_cmd() + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _rclone_remote_mtime(remote_path):
    import json

    cp = _rclone_run(["lsjson", remote_path], timeout=30)
    if cp.returncode != 0:
        stderr = (cp.stderr or "").strip()
        if stderr:
            _sync_log(f"rclone lsjson failed: {stderr}")
        return None
    try:
        payload = json.loads(cp.stdout or "[]")
    except ValueError:
        _sync_log("rclone lsjson returned invalid JSON")
        return None
    if isinstance(payload, dict):
        payload = [payload]
    if not payload:
        return None
    mod_time = payload[0].get("ModTime")
    if not mod_time:
        return None
    return datetime.fromisoformat(mod_time.replace("Z", "+00:00"))


def _rclone_copyto(src, dst):
    src_str = str(src)
    dst_str = str(dst)
    if isinstance(dst, Path):
        dst.parent.mkdir(parents=True, exist_ok=True)
    cp = _rclone_run(["copyto", src_str, dst_str], timeout=120)
    if cp.returncode == 0:
        return True
    stderr = (cp.stderr or cp.stdout or "").strip()
    if stderr:
        _sync_log(f"rclone copyto failed: {stderr}")
    return False


def _sync_db_with_gd_status(local_path):
    """Return 'pushed', 'in_sync', or 'failed' for the GD sync attempt."""
    try:
        gd_remote = _gd_db_remote()
        gd_time = _rclone_remote_mtime(gd_remote)
        if gd_time is None:
            _sync_log(f"{GD_FILENAME} not found on GD — creating")
            if _rclone_copyto(local_path, gd_remote):
                gd_time = _rclone_remote_mtime(gd_remote) or datetime.now(timezone.utc)
                _sync_log("created and uploaded")
                _write_sync_state(
                    SYNC_STATE_PATH,
                    gd_time.isoformat(),
                    gd_time,
                    local_path.stat().st_mtime,
                    _device_id(),
                )
                return "pushed"
            return "failed"
        local_time = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
        _sync_log(f"gd={gd_time}  local={local_time}")
        if local_time > gd_time:
            _sync_log("pushing to GD")
            if _rclone_copyto(local_path, gd_remote):
                new_time = _rclone_remote_mtime(gd_remote) or datetime.now(timezone.utc)
                _sync_log("push done")
                _write_sync_state(
                    SYNC_STATE_PATH,
                    new_time.isoformat(),
                    new_time,
                    local_path.stat().st_mtime,
                    _device_id(),
                )
                return "pushed"
            return "failed"
        else:
            _sync_log("already in sync or GD newer — skipping")
            return "in_sync"
    except Exception as e:
        _sync_log(f"error: {e}")
    return "failed"


def _sync_db_with_gd(local_path):
    """Push local DB to GD if local is newer. Record sync-state on success."""
    return _sync_db_with_gd_status(local_path) == "pushed"


def _decide_pull(local_state, gd_revision, local_db_mtime):
    """Pure decision function; returns one of:
    skip_unreachable, skip_no_state, skip_in_sync, pull, conflict."""
    if gd_revision is None:
        return "skip_unreachable"
    if local_state is None:
        return "skip_no_state"
    if gd_revision == local_state.get("revision_id"):
        return "skip_in_sync"
    # GD revision differs. Did local diverge?
    # Allow tiny float tolerance for mtime comparison.
    if local_db_mtime > local_state.get("local_mtime", 0) + 1.0:
        return "conflict"
    return "pull"


def _pull_db_from_gd():
    """Best-effort pull on startup. Never raises."""
    import os

    if os.environ.get("BLOG7_PULL_ON_START", "1") != "1":
        _sync_log("pull disabled by env flag")
        return
    try:
        gd_remote = _gd_db_remote()
        gd_time = _rclone_remote_mtime(gd_remote)
        gd_rev = gd_time.isoformat() if gd_time else None
        local_state = _read_sync_state(SYNC_STATE_PATH)
        local_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0
        decision = _decide_pull(local_state, gd_rev, local_mtime)
        _sync_log(f"pull decision: {decision}")
        if decision != "pull":
            return
        if _rclone_copyto(gd_remote, DB_PATH):
            gd_time = (
                _rclone_remote_mtime(gd_remote) or gd_time or datetime.now(timezone.utc)
            )
            _write_sync_state(
                SYNC_STATE_PATH, gd_rev, gd_time, DB_PATH.stat().st_mtime, _device_id()
            )
            _sync_log("pull done")
    except Exception as e:
        _sync_log(f"pull error: {e}")


# ── NS sync ───────────────────────────────────────────────────────────────────

_ISO_MONDAY = "date(day, '-' || cast((strftime('%w', day) + 6) % 7 as text) || ' days')"


def _update_summary_tables():
    db.execute(
        f"""
        INSERT OR REPLACE INTO daily (day, asset_id, income, expense, transfer_in, transfer_out, refund_return)
        SELECT day, asset_id,
               SUM(income), SUM(expense), SUM(transfer_in), SUM(transfer_out), SUM(refund_return)
        FROM transactions GROUP BY day, asset_id"""
    )
    db.execute(
        f"""
        INSERT OR REPLACE INTO weekly (week, asset_id, income, expense, transfer_in, transfer_out, refund_return)
        SELECT {_ISO_MONDAY} AS week, asset_id,
               SUM(income), SUM(expense), SUM(transfer_in), SUM(transfer_out), SUM(refund_return)
        FROM transactions GROUP BY week, asset_id"""
    )
    db.execute(
        """
        INSERT OR REPLACE INTO monthly (month, asset_id, income, expense, transfer_in, transfer_out, refund_return)
        SELECT substr(day,1,7) AS month, asset_id,
               SUM(income), SUM(expense), SUM(transfer_in), SUM(transfer_out), SUM(refund_return)
        FROM transactions GROUP BY month, asset_id"""
    )
    db.execute(
        """
        INSERT OR REPLACE INTO yearly (year, asset_id, income, expense, transfer_in, transfer_out, refund_return)
        SELECT substr(day,1,4) AS year, asset_id,
               SUM(income), SUM(expense), SUM(transfer_in), SUM(transfer_out), SUM(refund_return)
        FROM transactions GROUP BY year, asset_id"""
    )


def _ebt_desc(row):
    ttype = row.get("ttype_raw") or "Transaction"
    merchant = (row.get("merchant_name") or "").strip()

    # For purchases, show the merchant plainly, like the better parsed finance
    # descriptions, instead of prefixing every row with a long raw type label.
    if merchant and "purchase" in ttype.lower():
        return merchant

    # For benefit/deposit rows, keep the type because that is the meaningful part.
    if merchant:
        return f"{ttype}: {merchant}"

    return ttype


def _ebt_import_rows(rows, final_balance=None):
    db.execute("DELETE FROM transactions WHERE asset_id=?", [_EBT_ASSET_ID])

    inserted = 0

    for row in rows:
        # Rejected rows should not become live blog7 transactions.
        if row.get("rejected"):
            continue

        day = datetime.strptime(row["date"], "%m-%d-%Y").strftime("%Y-%m-%d")
        amt = round(row["amount_cents"] / 100, 2)
        credit = bool(row.get("credit"))
        signed_amt = amt if credit else -amt
        flow = 1 if credit else 2
        bucket = "income" if credit else "expense"
        db.execute(
            f"INSERT INTO transactions (id, asset_id, day, amt, flow, desc, {bucket}) VALUES (?,?,?,?,?,?,?)",
            [row["id"], _EBT_ASSET_ID, day, signed_amt, flow, _ebt_desc(row), amt],
        )
        inserted += 1

    if final_balance is not None:
        db.execute(
            "UPDATE asset SET current_balance=? WHERE asset_id=?",
            [round(final_balance, 2), _EBT_ASSET_ID],
        )

    _update_summary_tables()
    return inserted, final_balance


def _load_ebt_parser():
    import importlib.util

    # Keep blog7 self-contained.
    # The EBT CSV parser now lives inside this repo.
    parser_path = Path(__file__).parent / "scripts" / "ebt_csv_parser.py"

    if not parser_path.exists():
        raise FileNotFoundError(f"Could not locate blog7 EBT parser: {parser_path}")

    spec = importlib.util.spec_from_file_location("blog7_ebt_csv_parser", parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ebt_import_csv(csv_path, final_balance=None, rejection_path=None):
    parser = _load_ebt_parser()

    # If a rejection file was supplied, load it so rejected purchases stay out
    # of the live transaction table.
    rejections = set()
    if rejection_path:
        rejections = parser.load_rejections(rejection_path)

    rows = list(parser.parse_file(csv_path, rejections=rejections))
    return _ebt_import_rows(rows, final_balance=final_balance)


def _ebt_run_sync_script():
    import json
    import subprocess
    import sys

    # Keep the Flask-side wrapper simple:
    # - choose the output folder
    # - pass credentials if a local secrets file exists
    # - run the separate phone-side Playwright helper
    # - parse the JSON contract it returns
    out_dir = DATA_ROOT / "statements" / "ebtedge"
    script = Path(__file__).parent / "scripts" / "ebt_sync_playwright.py"
    env = None
    if EBT_CREDS_FILE.exists():
        try:
            creds = json.loads(EBT_CREDS_FILE.read_text(encoding="utf-8"))
            env = dict(os.environ)
            env["EBT_USER_ID"] = creds.get("user_id", "")
            env["EBT_PASSWORD"] = creds.get("password", "")
        except Exception:
            env = None
    cp = subprocess.run(
        [sys.executable, str(script), str(out_dir)],
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
        env=env,
    )
    return json.loads(cp.stdout)


def _ebt_do_sync():
    try:
        result = _ebt_run_sync_script()
        csv_path = result.get("csv_path")
        final_balance = result.get("final_balance")
        files_found = result.get("files_found") or {}

        if not csv_path:
            # If we have a real balance but no CSV yet, still keep the phone's
            # Colorado Quest balance current.
            if final_balance is not None:
                db.execute(
                    "UPDATE asset SET current_balance=? WHERE asset_id=?",
                    [round(final_balance, 2), _EBT_ASSET_ID],
                )
                return 0, final_balance, None
            found_parts = [name for name, present in files_found.items() if present]
            if found_parts:
                return (
                    0,
                    None,
                    "EBT sync found no CSV. Files found: " + ", ".join(found_parts),
                )
            return 0, None, "EBT sync produced no CSV."

        count, balance = _ebt_import_csv(
            csv_path,
            final_balance=final_balance,
            rejection_path=result.get("rejections_path"),
        )
        return count, balance, None
    except Exception as exc:
        return 0, None, f"EBT sync failed: {exc}"


def _ns_parse_ts(s: str) -> str:
    try:
        dt = datetime.strptime(s[:25], "%m-%d-%Y %H:%M:%S %z")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.strptime(s[:10], "%m-%d-%Y").strftime("%Y-%m-%dT00:00:00Z")


def _ns_ts_after(base_ts: str, offset_secs: int) -> str:
    dt = datetime.strptime(base_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (dt + timedelta(seconds=offset_secs)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ns_do_sync():
    """Returns (n, bal, err)."""
    if not TOKEN_FILE.exists():
        token = _silent_reauth()
        if not token:
            return 0, None, "No token and re-login failed."
    else:
        token = TOKEN_FILE.read_text().strip()
    if not token:
        return 0, None, "Token file is empty."

    hdrs = {**_NS_HEADERS, "X-Ns-Access_token": token}
    today = datetime.now()
    cur_d = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_d = cur_d - relativedelta(months=1)

    posted_txns = []
    final_bal = None

    for d in [prev_d, cur_d]:
        year, month = d.year, d.month
        url = f"{_NS_BASE}/webapi/v1/statement/debit/{year}/{month}"
        try:
            resp = requests.get(url, headers=hdrs, timeout=30)
            if resp.status_code in (401, 403):
                token = _silent_reauth()
                if not token:
                    return 0, None, "Token expired. Use NS Login."
                hdrs = {**_NS_HEADERS, "X-Ns-Access_token": token}
                resp = requests.get(url, headers=hdrs, timeout=30)
                if resp.status_code in (401, 403):
                    return (
                        0,
                        None,
                        "Token expired; re-login succeeded but still rejected.",
                    )
            resp.raise_for_status()
            stmt = resp.json()
        except requests.HTTPError as exc:
            return 0, None, f"HTTP {exc.response.status_code}"
        except Exception as exc:
            return 0, None, f"Network error: {exc}"

        for t in stmt.get("transactions", []):
            ts = _ns_parse_ts(t["date"])
            credit = t["credit"]
            amt = (
                round(t["amount"] / 100, 2) if credit else -round(t["amount"] / 100, 2)
            )
            bal = round(t["running_balance"] / 100, 2)
            memo = t.get("memo", "") or ""
            posted_txns.append((ts, amt, bal, "in" if credit else "ex", memo))

        if (year, month) == (today.year, today.month):
            ending = stmt.get("balance", {}).get("ending")
            if ending is not None:
                final_bal = round(ending / 100, 2)

    posted_txns.sort(key=lambda x: x[0])

    last_ts = (
        posted_txns[-1][0]
        if posted_txns
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    pending_txns = []
    try:
        resp = requests.get(
            f"{_NS_BASE}/webapi/v1/transactions/debit/pending", headers=hdrs, timeout=30
        )
        resp.raise_for_status()
        running = final_bal or 0.0
        for i, t in enumerate(resp.json().get("transactions", []), start=1):
            credit = t["credit"]
            amt = (
                round(t["amount"] / 100, 2) if credit else -round(t["amount"] / 100, 2)
            )
            running = round(running + amt, 2)
            memo = t.get("memo", "") or ""
            pending_txns.append(
                (_ns_ts_after(last_ts, i), amt, running, "in" if credit else "ex", memo)
            )
        if pending_txns:
            final_bal = running
    except Exception:
        pass

    all_txns = posted_txns + pending_txns
    db.execute("DELETE FROM transactions WHERE asset_id=?", [_NS_ASSET_ID])

    ft_rows = db.fetchall("SELECT flow, code FROM flow_types")
    code_to_flow = {r.code: r.flow for r in ft_rows}
    bucket_col = {
        "in": "income",
        "ex": "expense",
        "ti": "transfer_in",
        "to": "transfer_out",
        "rr": "refund_return",
    }
    sq = sqids_mod.Sqids()
    day_seqno = {}

    for ts, amt, bal, ft_code, memo in all_txns:
        flow = code_to_flow.get(ft_code, 2)
        dt_loc = (
            datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .astimezone()
        )
        day = dt_loc.strftime("%Y-%m-%d")
        dk = (dt_loc.year, dt_loc.month, dt_loc.day)
        day_seqno[dk] = day_seqno.get(dk, 0) + 1
        txn_id = sq.encode([_NS_ASSET_ID, dk[0], dk[1], dk[2], day_seqno[dk]])
        col = bucket_col.get(ft_code, "expense")
        db.execute(
            f"INSERT INTO transactions"
            f" (id, asset_id, day, amt, flow, balance, desc, {col})"
            f" VALUES (?,?,?,?,?,?,?,?)",
            [txn_id, _NS_ASSET_ID, day, amt, flow, bal, memo or None, amt],
        )

    if final_bal is not None:
        db.execute(
            "UPDATE asset SET current_balance=? WHERE asset_id=?",
            [final_bal, _NS_ASSET_ID],
        )

    _update_summary_tables()

    return len(all_txns), final_bal, None


# ── Routes ────────────────────────────────────────────────────────────────────


@app.route("/")
def balances():
    assets = db.load_assets()
    asset_id = request.args.get("asset", type=int, default=_NS_ASSET_ID)
    recent = db.fetchall(
        "SELECT id, day, amt, balance, flow FROM transactions"
        " WHERE asset_id=? ORDER BY day DESC, rowid DESC LIMIT 15",
        [asset_id],
    )
    ft_rows = db.fetchall("SELECT flow, code FROM flow_types")
    flow_code = {r.flow: r.code for r in ft_rows}
    focused = next(
        (a for a in assets if a["id"] == asset_id), assets[0] if assets else None
    )
    return render_template(
        "balances.html",
        tab="balances",
        assets=assets,
        recent=recent,
        flow_code=flow_code,
        focused=focused,
        ncs=ncs,
    )


@app.route("/update", methods=["POST"])
def update():
    assets = db.load_assets()
    bal_map = {a["id"]: a["balance"] for a in assets}
    for a in assets:
        field_val = request.form.get(f"bal_{a['id']}", "").strip()
        items = txtpa(field_val)
        if not items:
            continue
        acc = 0.0
        for item in items:
            prev = bal_map[a["id"]] if acc == 0.0 else acc
            acc = nc(acc + item["num"])
            if bal_map[a["id"]] != acc:
                bal_map[a["id"]] = acc
                db.save_asset_balance(a["id"], acc)
                if item["tag"] in ("ti", "to", "rr"):
                    tag = item["tag"]
                else:
                    tag = "in" if acc >= prev else "ex"
                db.log_txn(a["id"], item["num"], acc, tag)
    _update_summary_tables()
    flash("Updated.", "ok")
    return redirect(url_for("balances"))


@app.route("/sync_ns", methods=["POST"])
def sync_ns():
    n, bal, err = _ns_do_sync()
    if err:
        flash(err, "err")
    else:
        ts = datetime.now().strftime("%m/%d %H:%M")
        bal_str = f"  bal=${bal:.2f}" if bal is not None else ""
        flash(f"Synced {ts} — {n} entries{bal_str}", "ok")
    return redirect(url_for("balances"))


@app.route("/sync_ebt", methods=["POST"])
def sync_ebt():
    n, bal, err = _ebt_do_sync()
    if err:
        _sync_log(err)
        flash(err, "err")
    else:
        bal_str = f"  bal=${bal:.2f}" if bal is not None else ""
        if n == 0 and bal is not None:
            flash(f"Updated EBT balance only{bal_str}", "ok")
        else:
            flash(f"Synced EBT - {n} entries{bal_str}", "ok")
    return redirect(url_for("balances", asset=_EBT_ASSET_ID))


@app.route("/login_ns", methods=["GET", "POST"])
def login_ns():
    if request.method == "GET":
        un, pw = _read_creds()
        return render_template("login.html", tab="balances", prefill_un=un or "")
    un = request.form.get("username", "").strip()
    pw = request.form.get("password", "").strip()
    if not un or not pw:
        flash("Enter username and password.", "err")
        return redirect(url_for("login_ns"))
    try:
        data = _do_login_request(un, pw)
    except Exception as exc:
        flash(f"Login error: {exc}", "err")
        return redirect(url_for("login_ns"))
    token = data.get("token", "")
    if data.get("ooba_required"):
        session["ooba_token"] = token
        session["ooba_username"] = un
        session["ooba_password"] = pw
        return redirect(url_for("ooba"))
    if token:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token)
        CREDS_FILE.write_text(f"{un}\n{pw}\n")
        flash("Logged in.", "ok")
        return redirect(url_for("balances"))
    flash(f"Unexpected response: {data}", "err")
    return redirect(url_for("login_ns"))


@app.route("/ooba", methods=["GET", "POST"])
def ooba():
    if request.method == "GET":
        return render_template("ooba.html", tab="balances")
    code = request.form.get("code", "").strip()
    partial_token = session.get("ooba_token", "")
    try:
        resp = requests.post(
            "https://www.netspend.com/profile-api/ooba/verify",
            headers={**_NS_LOGIN_HEADERS, "X-Ns-Access_token": partial_token},
            json={"ooba_passcode": code},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        flash(f"Verification error: {exc}", "err")
        return redirect(url_for("ooba"))
    token = data.get("token") or partial_token
    if token:
        TOKEN_FILE.write_text(token)
        un = session.get("ooba_username", "")
        pw = session.get("ooba_password", "")
        if un and pw:
            CREDS_FILE.write_text(f"{un}\n{pw}\n")
        flash("Logged in.", "ok")
        return redirect(url_for("balances"))
    flash(f"Verification failed: {data}", "err")
    return redirect(url_for("ooba"))


@app.route("/delete_txn/<path:txn_id>")
def delete_txn(txn_id):
    asset_id = request.args.get("asset", type=int, default=_NS_ASSET_ID)
    db.execute("DELETE FROM transactions WHERE id=?", [txn_id])
    _update_summary_tables()
    return redirect(url_for("balances", asset=asset_id))


@app.route("/calcs")
def calcs():
    assets = db.load_assets()
    ebt_ids = [a["id"] for a in assets if a["ebt"]]
    sources = db.load_sources(ebt_ids)

    if ebt_ids:
        ph = ",".join("?" * len(ebt_ids))
        excl = f" AND asset_id NOT IN ({ph})"
    else:
        excl = ""

    def spendable():
        return sum(a["balance"] for a in assets if not a["ebt"])

    dl_rows = db.fetchall(
        f"SELECT day FROM source WHERE day IS NOT NULL AND day != ''{excl}", ebt_ids
    )
    days_left_vals = [dl(int(r.day)) for r in dl_rows if r.day and int(r.day) > 0]
    maxdl = sum(days_left_vals) / len(days_left_vals) if days_left_vals else 30.0
    spend = spendable()
    dallow = spend / maxdl if maxdl > 0 else 0.0

    rows = db.fetchall(
        "SELECT day AS ts, SUM(CASE WHEN flow IN (2,5) THEN amt ELSE 0 END) AS net"
        " FROM transactions WHERE day IS NOT NULL"
        + excl
        + " GROUP BY day HAVING net != 0 ORDER BY day ASC",
        ebt_ids,
    )
    rc = len(rows)
    davg = 0.0
    dtot = 0.0
    dtot_label = ""
    if rc >= 1:
        sc = min(29, rc - 1)
        te = sum(rows[i].net for i in range(rc - sc - 1, rc))
        davg = -te / (sc + 1)
        dtot = -rows[-1].net
        dtot_label = rows[-1].ts

    tleft = spend / davg if davg > 0 else 999.0
    inec = (davg - dallow) * maxdl

    dl_items = []
    for s in sources:
        if s["day"] and int(s["day"]) > 0:
            days = dl(int(s["day"]))
            dl_items.append(
                f"{int(round(days))} days left until {s['name']} {s['type']}"
            )

    calcs_data = [
        ("DAllow", "Daily Allowance", ncs(dallow), "pink"),
        ("INec", "Income Needed", ncs(inec), "green"),
        ("TLeft", "Days Left", ncs(tleft), "red"),
        ("DAvgExp", "Avg Daily Exp", ncs(davg), "teal"),
        ("DTotExp", "Today Expense", ncs(dtot), "blue"),
        ("MaxDL", "Max Days Left", ncs(maxdl), "grey"),
    ]
    for key, val in [
        ("DAllow", dallow),
        ("INec", inec),
        ("TLeft", tleft),
        ("DAvgExp", davg),
        ("DTotExp", dtot),
        ("MaxDL", maxdl),
    ]:
        db.save_number(key, val)
    return render_template(
        "calcs.html",
        tab="calcs",
        calcs=calcs_data,
        dl_items=dl_items,
        dtot_label=dtot_label,
    )


@app.route("/transactions")
def transactions():
    allowed = {"day", "label", "asset_id", "flow", "amt", "balance"}
    sort_col = request.args.get("sort", "day")
    if sort_col not in allowed:
        sort_col = "day"
    asc = request.args.get("asc", "0") == "1"
    direction = "ASC" if asc else "DESC"

    assets = db.load_assets()
    asset_name_map = {a["id"]: a["name"] for a in assets}
    ft_rows = db.fetchall("SELECT flow, name FROM flow_types")
    flow_name_map = {r.flow: r.name for r in ft_rows}

    rows = db.fetchall(
        f"SELECT id, day, COALESCE(comp, desc) AS label, asset_id, flow, amt, balance"
        f" FROM transactions ORDER BY {sort_col} {direction}, rowid DESC"
    )

    return render_template(
        "transactions.html",
        tab="transactions",
        rows=rows,
        asset_name_map=asset_name_map,
        flow_name_map=flow_name_map,
        sort_col=sort_col,
        asc=asc,
    )


_SUMMARY_LIMITS = {"daily": 40, "weekly": 40, "monthly": 40, "yearly": 40}


def _summary_route(tbl, period_col, title, tab):
    assets = db.load_assets()
    asset_name_map = {a["id"]: a["name"] for a in assets}
    limit = _SUMMARY_LIMITS.get(tbl, 60)
    # Get most recent N distinct periods, then fetch all rows for those periods
    periods_q = db.fetchall(
        f"SELECT DISTINCT {period_col} FROM {tbl} ORDER BY {period_col} DESC LIMIT ?",
        [limit],
    )
    if not periods_q:
        rows = []
    else:
        placeholders = ",".join("?" * len(periods_q))
        period_vals = [r[period_col] for r in periods_q]
        rows = db.fetchall(
            f"SELECT {period_col}, asset_id, income, expense, transfer_in, transfer_out, refund_return"
            f" FROM {tbl} WHERE {period_col} IN ({placeholders}) ORDER BY {period_col} DESC",
            period_vals,
        )

    # Collect ordered periods; always show all assets as columns
    asset_ids = [a["id"] for a in assets]
    periods = []
    pivot = {}
    for r in rows:
        p = r[period_col]
        if p not in pivot:
            pivot[p] = {}
            periods.append(p)
        pivot[p][r.asset_id] = (
            r.income,
            r.expense,
            r.transfer_in,
            r.transfer_out,
            r.refund_return,
        )

    return render_template(
        "summary.html",
        tab=tab,
        title=title,
        period_col=period_col,
        periods=periods,
        asset_ids=asset_ids,
        pivot=pivot,
        asset_name_map=asset_name_map,
    )


@app.route("/daily")
def daily():
    return _summary_route("daily", "day", "Daily", "daily")


@app.route("/weekly")
def weekly():
    return _summary_route("weekly", "week", "Weekly", "weekly")


@app.route("/monthly")
def monthly():
    return _summary_route("monthly", "month", "Monthly", "monthly")


@app.route("/yearly")
def yearly():
    return _summary_route("yearly", "year", "Yearly", "yearly")


@app.route("/exit")
def exit_app():
    try:
        shutil.copy2(str(DB_PATH), str(DB_BAK))
        backed_up = True
    except Exception:
        backed_up = False
    sync_status = _sync_db_with_gd_status(DB_PATH)
    return render_template("exit.html", backed_up=backed_up, sync_status=sync_status)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_creds():
    if not CREDS_FILE.exists():
        return None, None
    lines = CREDS_FILE.read_text().splitlines()
    if len(lines) >= 2:
        return lines[0].strip(), lines[1].strip()
    return None, None


def _do_login_request(username, password):
    """Blocking login — returns response dict or raises."""
    s = requests.Session()
    s.headers.update(_NS_LOGIN_HEADERS)
    s.get("https://www.netspend.com/account/login", timeout=15)
    resp = s.post(
        _NS_LOGIN_URL,
        json={
            "username": username,
            "password": password,
            "auth_type": "password",
            "device_fingerprint": _NS_DEVICE_FP,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _silent_reauth():
    """Re-login with saved creds. Returns new token str, or None on failure."""
    un, pw = _read_creds()
    if not (un and pw):
        return None
    try:
        data = _do_login_request(un, pw)
    except Exception:
        return None
    if data.get("ooba_required"):
        return None
    token = data.get("token", "")
    if token:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token)
    return token or None


if __name__ == "__main__":
    try:
        _pull_db_from_gd()
    except Exception as _e:
        _sync_log(f"startup pull crashed: {_e}")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
