# GDrive Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Google Drive the durable vault and sync bus for all blog7 data; move DBs and statement archives out of the project repo; enable laptop→phone data flow via GD; preserve phone offline-first behavior.

**Architecture:** Each device reads/writes a local `blog7.db`. A sync-state sidecar (`blog7.db.sync-state.json`) tracks GD's last-known revision so pulls can detect "safe" vs "conflicting" states without relying on flaky GD mtimes. Push happens on `/exit`; pull happens best-effort on app startup. Cold data (statements, `finance.db`) is one-way pushed to GD via `rclone sync`.

**Tech Stack:** Python 3, Flask, rclone (CLI for ops, REST API already in app.py for app-driven sync), SQLite, Google Drive v3 API.

**Source spec:** `docs/superpowers/specs/2026-04-18-gdrive-data-migration-design.md` — read it before starting.

**Resumability:** This plan is large and likely spans multiple sessions. Each task is self-contained. Before ending a session mid-plan, update this plan file's checkboxes, commit, and stash a progress memory with what's done and what's next.

---

## Conventions used in this plan

- **"laptop shell"** = bash on Windows laptop (`~/projects/blog7` = `C:\Users\donal\projects\blog7`).
- **"phone shell"** = Termux on phone (reach via SSH per memory `phone_ssh_access.md`, or via ADB).
- **GD root folder** = `Blog7` (capital B — existing folder, do not rename). New subfolders: `Blog7/db/`, `Blog7/statements/`, `Blog7/secrets/`.
- **rclone remote** = whatever the existing `rclone.conf` defines; verify with `rclone listremotes`. Examples below use `gd:` — substitute the real remote name.

---

## Task 1: Inventory & backup

**Purpose:** Create a dated safety snapshot of everything before touching anything.

**Files:**
- Create: `~/blog7-migration-backup-2026-04-18/` (laptop)

**Steps:**

- [ ] **Step 1.1:** Verify rclone remote name.

```bash
rclone listremotes --config ~/projects/finance/rclone.conf
```
Expected: one line ending with `:` — note the name (e.g. `gd:`). Use this as `REMOTE` below.

- [ ] **Step 1.2:** Create backup directory.

```bash
mkdir -p ~/blog7-migration-backup-2026-04-18
```

- [ ] **Step 1.3:** Copy laptop DBs and credentials into the backup.

```bash
cp ~/projects/finance/blog7.db ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/blog7_backup.db ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/finance.db ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/rclone.conf ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/ns_token.txt ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/ns_token_laptop.txt ~/blog7-migration-backup-2026-04-18/
cp ~/projects/finance/ns_creds.txt ~/blog7-migration-backup-2026-04-18/
```

- [ ] **Step 1.4:** Archive statements tree.

```bash
tar czf ~/blog7-migration-backup-2026-04-18/statements.tar.gz -C ~/projects/finance statements
```

- [ ] **Step 1.5:** Pull the phone's current `blog7.db` for safety (via SSH per `phone_ssh_access.md`).

```bash
scp -P 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53:/sdcard/Android/data/com.termux/files/blog7/blog7.db ~/blog7-migration-backup-2026-04-18/blog7.db.phone
```
If the phone is unreachable, log this in sync.log-style and proceed — but do NOT proceed past Task 2 without a phone backup.

- [ ] **Step 1.6:** Verify.

```bash
ls -la ~/blog7-migration-backup-2026-04-18/
```
Expected: both laptop DBs, three credential files, `statements.tar.gz`, and (if reachable) `blog7.db.phone`.

- [ ] **Step 1.7:** Commit a marker to the blog7 repo.

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: backup snapshot at ~/blog7-migration-backup-2026-04-18"
```

---

## Task 2: Create GD layout and push current data

**Purpose:** Stand up the target folder structure on Google Drive and populate it from the laptop's current data. Checkpoint for user confirmation at the end.

**Steps:**

- [ ] **Step 2.1:** Confirm existing GD `Blog7` folder.

```bash
rclone --config ~/projects/finance/rclone.conf lsf gd: | grep -i '^Blog7'
```
Expected: `Blog7/` line present.

- [ ] **Step 2.2:** Create the three subfolders.

```bash
rclone --config ~/projects/finance/rclone.conf mkdir gd:Blog7/db
rclone --config ~/projects/finance/rclone.conf mkdir gd:Blog7/statements
rclone --config ~/projects/finance/rclone.conf mkdir gd:Blog7/secrets
```

- [ ] **Step 2.3:** Move existing `blog7.db` into `Blog7/db/`.

```bash
rclone --config ~/projects/finance/rclone.conf moveto gd:Blog7/blog7.db gd:Blog7/db/blog7.db
```

**IMPORTANT:** After this, the existing app's `/exit` push will fail until Task 5 is deployed (because the app looks at `Blog7/blog7.db` not `Blog7/db/blog7.db`). Warn the user — don't use `/exit` between now and Task 5/6 deploy.

- [ ] **Step 2.4:** Upload `finance.db` to `Blog7/db/`.

```bash
rclone --config ~/projects/finance/rclone.conf copy ~/projects/finance/finance.db gd:Blog7/db/
```

- [ ] **Step 2.5:** Upload the statements tree.

```bash
rclone --config ~/projects/finance/rclone.conf sync ~/projects/finance/statements gd:Blog7/statements
```
Expected: transfer runs, final "Transferred:" line shows the expected size.

- [ ] **Step 2.6:** Upload credentials as recovery copies.

```bash
rclone --config ~/projects/finance/rclone.conf copy ~/projects/finance/rclone.conf       gd:Blog7/secrets/
rclone --config ~/projects/finance/rclone.conf copy ~/projects/finance/ns_token.txt       gd:Blog7/secrets/
rclone --config ~/projects/finance/rclone.conf copy ~/projects/finance/ns_token_laptop.txt gd:Blog7/secrets/
rclone --config ~/projects/finance/rclone.conf copy ~/projects/finance/ns_creds.txt       gd:Blog7/secrets/
```

- [ ] **Step 2.7:** Verify GD layout.

```bash
rclone --config ~/projects/finance/rclone.conf lsf -R gd:Blog7/ | head -40
```
Expected: `db/blog7.db`, `db/finance.db`, `statements/...`, `secrets/rclone.conf`, etc.

- [ ] **Step 2.8:** Commit plan progress.

```bash
git -C ~/projects/blog7 add docs/superpowers/plans/2026-04-18-gdrive-data-migration.md && git -C ~/projects/blog7 commit -m "migration: task 2 complete — GD layout populated"
```

- [ ] **CHECKPOINT:** Stop here and have the user confirm GD contents before proceeding. This is the last fully-reversible state.

---

## Task 3: Laptop local reorg to ~/blog7-data/

**Purpose:** Move laptop-side data out of `~/projects/finance/` into a dedicated data root. Leave parser code in place.

**Files:**
- Create: `~/blog7-data/` tree
- Moved: `~/projects/finance/{blog7.db,blog7_backup.db,finance.db,statements/,rclone.conf,ns_token*.txt,ns_creds.txt,sync.log}`

**Steps:**

- [ ] **Step 3.1:** Create the new data root.

```bash
mkdir -p ~/blog7-data/db ~/blog7-data/statements ~/blog7-data/secrets
```

- [ ] **Step 3.2:** Move DBs.

```bash
mv ~/projects/finance/blog7.db         ~/blog7-data/db/
mv ~/projects/finance/blog7_backup.db  ~/blog7-data/db/
mv ~/projects/finance/finance.db       ~/blog7-data/db/
```

- [ ] **Step 3.3:** Move statements tree.

```bash
mv ~/projects/finance/statements ~/blog7-data/statements-tmp && rmdir ~/blog7-data/statements && mv ~/blog7-data/statements-tmp ~/blog7-data/statements
```

- [ ] **Step 3.4:** Move credentials.

```bash
mv ~/projects/finance/rclone.conf         ~/blog7-data/secrets/
mv ~/projects/finance/ns_token.txt        ~/blog7-data/secrets/
mv ~/projects/finance/ns_token_laptop.txt ~/blog7-data/secrets/
mv ~/projects/finance/ns_creds.txt        ~/blog7-data/secrets/
```

- [ ] **Step 3.5:** Move (or rename) the sync log.

```bash
mv ~/projects/finance/blog7_sync.log ~/blog7-data/sync.log 2>/dev/null || touch ~/blog7-data/sync.log
```

- [ ] **Step 3.6:** Leave transition symlinks so anything still pointing at old paths keeps working until Task 4 lands.

```bash
ln -s ~/blog7-data/db/blog7.db           ~/projects/finance/blog7.db
ln -s ~/blog7-data/db/blog7_backup.db    ~/projects/finance/blog7_backup.db
ln -s ~/blog7-data/db/finance.db         ~/projects/finance/finance.db
ln -s ~/blog7-data/statements            ~/projects/finance/statements
ln -s ~/blog7-data/secrets/rclone.conf   ~/projects/finance/rclone.conf
ln -s ~/blog7-data/secrets/ns_token.txt  ~/projects/finance/ns_token.txt
ln -s ~/blog7-data/secrets/ns_token_laptop.txt ~/projects/finance/ns_token_laptop.txt
ln -s ~/blog7-data/secrets/ns_creds.txt  ~/projects/finance/ns_creds.txt
ln -s ~/blog7-data/sync.log              ~/projects/finance/blog7_sync.log
```

Note: On Windows bash, `ln -s` creates NTFS symlinks when run with the right privileges. If it fails with "permission denied", retry in an elevated shell or use `mklink` equivalents. If symlinks cannot be created, abort Task 3 and revert by moving files back — Task 4 becomes a hard prerequisite to proceed.

- [ ] **Step 3.7:** Smoke-test the app still starts with the old paths (via symlinks).

```bash
cd ~/projects/blog7 && python -c "from pathlib import Path; p = Path.home()/'projects/finance/blog7.db'; print('ok' if p.exists() else 'MISSING')"
```
Expected: `ok`.

- [ ] **Step 3.8:** Commit.

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: task 3 complete — laptop data moved to ~/blog7-data/ with transition symlinks"
```

---

## Task 4: Refactor app.py paths to DATA_ROOT

**Purpose:** Collapse the scattered path constants (app.py:33–48) into one `DATA_ROOT` + derived subpaths. Phone path shape changes to match laptop (adds `db/`, `secrets/` subdirs).

**Files:**
- Modify: `~/projects/blog7/app.py:33-48`
- Create: `~/projects/blog7/tests/test_data_paths.py` (new, small)

**Steps:**

- [ ] **Step 4.1:** Write a test for the new path constants.

Create `tests/test_data_paths.py`:

```python
"""Verify DATA_ROOT and derived subpaths."""
import os
from pathlib import Path
import importlib.util


def _load_app(monkeypatch, tmp_path, android):
    """Import app.py with a fake DATA_ROOT and platform flag."""
    spec = importlib.util.spec_from_file_location(
        "app_under_test", Path(__file__).parent.parent / "app.py")
    # Can't easily import Flask app without side effects; instead,
    # exec the first 60 lines in isolation to grab the path block.
    src = (Path(__file__).parent.parent / "app.py").read_text()
    header = src.split("# ── NS API constants")[0]
    ns = {"__file__": str(Path(__file__).parent.parent / "app.py")}
    # force the android branch
    if android:
        # fake an existing android root
        fake = tmp_path / "blog7"
        fake.mkdir()
        monkeypatch.setattr("pathlib.Path.exists",
            lambda self: str(self) == str(fake) or Path._exists_orig(self))
    exec(header, ns)
    return ns


def test_laptop_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    # Ensure android path does NOT exist
    android_root = Path("/sdcard/Android/data/com.termux/files/blog7")
    if android_root.exists():
        # running on an actual android — skip
        import pytest; pytest.skip("running on android")
    src = (Path(__file__).parent.parent / "app.py").read_text()
    header = src.split("# ── NS API constants")[0]
    ns = {"__file__": "x"}
    exec(header, ns)
    assert ns["DATA_ROOT"] == tmp_path / "blog7-data"
    assert ns["DB_PATH"] == tmp_path / "blog7-data/db/blog7.db"
    assert ns["DB_BAK"] == tmp_path / "blog7-data/db/blog7_backup.db"
    assert ns["RCLONE_CONF"] == tmp_path / "blog7-data/secrets/rclone.conf"
    assert ns["TOKEN_FILE"] == tmp_path / "blog7-data/secrets/ns_token.txt"
    assert ns["CREDS_FILE"] == tmp_path / "blog7-data/secrets/ns_creds.txt"
    assert ns["SYNC_LOG"] == tmp_path / "blog7-data/sync.log"
    assert ns["SYNC_STATE_PATH"] == tmp_path / "blog7-data/db/blog7.db.sync-state.json"
```

- [ ] **Step 4.2:** Run the test — expect failure.

```bash
cd ~/projects/blog7 && python -m pytest tests/test_data_paths.py -v
```
Expected: FAIL (`DATA_ROOT` and `SYNC_STATE_PATH` don't exist yet; also `TOKEN_FILE` current laptop path is `ns_token_laptop.txt` not `ns_token.txt`).

- [ ] **Step 4.3:** Replace app.py:33–48 with the consolidated block.

```python
# ── Platform detection & data root ───────────────────────────────────────────

_ANDROID_ROOT = Path("/sdcard/Android/data/com.termux/files/blog7")
ANDROID = _ANDROID_ROOT.exists()
if ANDROID:
    DATA_ROOT = _ANDROID_ROOT
else:
    DATA_ROOT = Path.home() / "blog7-data"

DB_PATH         = DATA_ROOT / "db" / "blog7.db"
DB_BAK          = DATA_ROOT / "db" / "blog7_backup.db"
SYNC_STATE_PATH = DATA_ROOT / "db" / "blog7.db.sync-state.json"
TOKEN_FILE      = DATA_ROOT / "secrets" / "ns_token.txt"
CREDS_FILE      = DATA_ROOT / "secrets" / "ns_creds.txt"
RCLONE_CONF     = DATA_ROOT / "secrets" / "rclone.conf"
SYNC_LOG        = DATA_ROOT / "sync.log"
```

- [ ] **Step 4.4:** Ensure phone data root has the new subdir layout.

Via SSH to the phone:

```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 '
ROOT=/sdcard/Android/data/com.termux/files/blog7
mkdir -p $ROOT/db $ROOT/secrets
[ -f $ROOT/blog7.db ]            && mv $ROOT/blog7.db            $ROOT/db/
[ -f $ROOT/blog7_backup.db ]     && mv $ROOT/blog7_backup.db     $ROOT/db/
[ -f $ROOT/rclone.conf ]         && mv $ROOT/rclone.conf         $ROOT/secrets/
[ -f $ROOT/ns_token.txt ]        && mv $ROOT/ns_token.txt        $ROOT/secrets/
[ -f $ROOT/ns_creds.txt ]        && mv $ROOT/ns_creds.txt        $ROOT/secrets/
ls -la $ROOT/db $ROOT/secrets
'
```

Do NOT restart the phone app yet — its app.py still expects the old paths. Task 7 cuts the phone over.

- [ ] **Step 4.5:** Run the test again — expect pass.

```bash
cd ~/projects/blog7 && python -m pytest tests/test_data_paths.py -v
```
Expected: PASS.

- [ ] **Step 4.6:** Laptop smoke test — start the app, browse to a page, quit.

```bash
cd ~/projects/blog7 && python app.py &
sleep 3
curl -s http://localhost:5000/ | head -5
kill %1
```
Expected: HTML returned; no stack trace in the terminal.

- [ ] **Step 4.7:** Commit.

```bash
git -C ~/projects/blog7 add app.py tests/test_data_paths.py && git -C ~/projects/blog7 commit -m "migration: consolidate data paths behind DATA_ROOT"
```

---

## Task 5: Push logic with sync-state sidecar

**Purpose:** Extend the existing push path (app.py:505–529) so each successful upload records a sync-state sidecar locally and on GD. Adjust `_gd_find_file`/`_gd_create_file` to look under `Blog7/db/` instead of `Blog7/` root.

**Files:**
- Modify: `~/projects/blog7/app.py` — add `_gd_db_folder_id()`, refactor `_gd_find_file`/`_gd_create_file` to accept a parent folder, add sync-state write helpers, extend `_sync_db_with_gd`.
- Create: `~/projects/blog7/tests/test_sync_state.py`

**Steps:**

- [ ] **Step 5.1:** Write failing test for sync-state write/read helpers.

`tests/test_sync_state.py`:

```python
"""Verify the sync-state sidecar helpers."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_write_sync_state(tmp_path):
    from app import _write_sync_state
    p = tmp_path / "blog7.db.sync-state.json"
    _write_sync_state(
        path=p,
        revision_id="abc123",
        gd_modified_time=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
        local_mtime=1_700_000_000.0,
        device="laptop",
    )
    data = json.loads(p.read_text())
    assert data["revision_id"] == "abc123"
    assert data["gd_modified_time"] == "2026-04-18T12:00:00+00:00"
    assert data["local_mtime"] == 1_700_000_000.0
    assert data["device"] == "laptop"


def test_read_sync_state_missing(tmp_path):
    from app import _read_sync_state
    assert _read_sync_state(tmp_path / "does-not-exist.json") is None


def test_read_sync_state_roundtrip(tmp_path):
    from app import _read_sync_state, _write_sync_state
    p = tmp_path / "ss.json"
    _write_sync_state(
        path=p, revision_id="r", gd_modified_time=datetime.now(timezone.utc),
        local_mtime=1.0, device="phone",
    )
    out = _read_sync_state(p)
    assert out["revision_id"] == "r"
    assert out["device"] == "phone"
```

- [ ] **Step 5.2:** Run it — expect `ImportError: cannot import name '_write_sync_state'`.

```bash
cd ~/projects/blog7 && python -m pytest tests/test_sync_state.py -v
```

- [ ] **Step 5.3:** Add the sync-state helpers to app.py, near the other GD helpers (around line 375, just before `_sync_log`).

```python
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
```

- [ ] **Step 5.4:** Add a `_gd_db_folder_id()` helper that returns the `Blog7/db/` folder id (or None). Place after `_gd_folder_id()`.

```python
def _gd_db_folder_id():
    """Return the Drive folder ID for Blog7/db, or None."""
    headers = _gd_headers()
    if not headers:
        return None
    parent = _gd_folder_id()
    if not parent:
        return None
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={"q": (f"name='db' and mimeType='application/vnd.google-apps.folder' "
                      f"and '{parent}' in parents and trashed=false"),
                "fields": "files(id)", "spaces": "drive"},
        timeout=15)
    files = r.json().get("files", []) if r.status_code == 200 else []
    return files[0]["id"] if files else None
```

- [ ] **Step 5.5:** Refactor `_gd_find_file` and `_gd_create_file` to take a parent folder id parameter, default to `_gd_db_folder_id()`. Update all call sites. Also change `_gd_find_file` to return `(file_id, modified_time, revision_id)` — add `revisionId` to the `fields` param.

Replace app.py:450–503 with:

```python
def _gd_find_file(filename=None, parent_id=None):
    headers = _gd_headers()
    if not headers:
        return None, None, None
    if filename is None:
        filename = GD_FILENAME
    if parent_id is None:
        parent_id = _gd_db_folder_id()
    q = f"name='{filename}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={"q": q,
                "fields": "files(id,name,modifiedTime,headRevisionId)",
                "spaces": "drive"},
        timeout=15)
    if r.status_code != 200:
        _sync_log(f"find failed: {r.status_code}")
        return None, None, None
    files = r.json().get("files", [])
    if not files:
        return None, None, None
    f = files[0]
    mt = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
    return f["id"], mt, f.get("headRevisionId")

def _gd_upload(file_id, src_path):
    headers = _gd_headers()
    with open(str(src_path), "rb") as f:
        r = requests.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{file_id}",
            headers={**headers, "Content-Type": "application/octet-stream"},
            params={"uploadType": "media", "fields": "id,modifiedTime,headRevisionId"},
            data=f, timeout=60)
    if r.status_code == 200:
        body = r.json()
        mt = datetime.fromisoformat(body["modifiedTime"].replace("Z", "+00:00"))
        return True, mt, body.get("headRevisionId")
    _sync_log(f"upload failed: {r.status_code}")
    return False, None, None

def _gd_create_file(src_path, filename=None, parent_id=None):
    headers = _gd_headers()
    if filename is None:
        filename = GD_FILENAME
    if parent_id is None:
        parent_id = _gd_db_folder_id()
    meta = {"name": filename}
    if parent_id:
        meta["parents"] = [parent_id]
    r = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers, json=meta, timeout=15)
    if r.status_code != 200:
        _sync_log(f"create failed: {r.status_code}")
        return None, None, None
    file_id = r.json().get("id")
    if not file_id:
        return None, None, None
    ok, mt, rev = _gd_upload(file_id, src_path)
    return (file_id, mt, rev) if ok else (None, None, None)
```

- [ ] **Step 5.6:** Rewrite `_sync_db_with_gd` to record sync-state on success.

```python
def _sync_db_with_gd(local_path):
    """Push local DB to GD if local is newer. Record sync-state on success."""
    try:
        file_id, gd_time, gd_rev = _gd_find_file()
        if not file_id:
            _sync_log(f"{GD_FILENAME} not found on GD — creating")
            file_id, gd_time, gd_rev = _gd_create_file(local_path)
            if file_id:
                _sync_log("created and uploaded")
                _write_sync_state(SYNC_STATE_PATH, gd_rev, gd_time,
                                  local_path.stat().st_mtime, _device_id())
                return True
            return False
        local_time = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
        _sync_log(f"gd={gd_time}  local={local_time}")
        if local_time > gd_time:
            _sync_log("pushing to GD")
            ok, new_time, new_rev = _gd_upload(file_id, local_path)
            if ok:
                _sync_log("push done")
                _write_sync_state(SYNC_STATE_PATH, new_rev, new_time,
                                  local_path.stat().st_mtime, _device_id())
                return True
        else:
            _sync_log("already in sync or GD newer — skipping")
    except Exception as e:
        _sync_log(f"error: {e}")
    return False
```

- [ ] **Step 5.7:** Run the unit test — expect PASS.

```bash
cd ~/projects/blog7 && python -m pytest tests/test_sync_state.py -v
```

- [ ] **Step 5.8:** Integration check against real GD (laptop). Start the app, make a trivial DB edit (e.g. via `/exit` route or any mutation), then check that `~/blog7-data/db/blog7.db.sync-state.json` was created and contains a `revision_id`.

```bash
cd ~/projects/blog7 && python app.py &
sleep 3
curl -s http://localhost:5000/exit >/dev/null
kill %1 2>/dev/null
cat ~/blog7-data/db/blog7.db.sync-state.json
```
Expected: JSON blob with `revision_id`, `gd_modified_time`, `local_mtime`, `device: "laptop"`.

- [ ] **Step 5.9:** Commit.

```bash
git -C ~/projects/blog7 add app.py tests/test_sync_state.py && git -C ~/projects/blog7 commit -m "migration: sync-state sidecar on push; GD paths moved to Blog7/db/"
```

---

## Task 6: Pull-on-startup with conflict detection

**Purpose:** Add best-effort pull logic that runs once on app startup. Honor the conflict rules from the spec. Feature-flag it for per-device control. Checkpoint for user confirmation at the end.

**Files:**
- Modify: `~/projects/blog7/app.py` — add `_gd_download`, `_pull_db_from_gd`, wire into startup, add `BLOG7_PULL_ON_START` env-var flag.
- Modify: `~/projects/blog7/tests/test_sync_state.py` — add tests for conflict detection logic.

**Steps:**

- [ ] **Step 6.1:** Write failing tests for the pure conflict-decision function.

Append to `tests/test_sync_state.py`:

```python
def test_decide_pull_no_local_state():
    from app import _decide_pull
    # No local sync-state → can't tell if safe; fall back to "skip" to protect local.
    assert _decide_pull(local_state=None, gd_revision="r1",
                        local_db_mtime=1.0) == "skip_no_state"


def test_decide_pull_gd_same_as_local():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision="r1", local_db_mtime=1.0) == "skip_in_sync"


def test_decide_pull_safe_to_pull():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision="r2", local_db_mtime=1.0) == "pull"


def test_decide_pull_conflict():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    # Local db has been modified since last sync AND GD has moved.
    assert _decide_pull(state, gd_revision="r2", local_db_mtime=5.0) == "conflict"


def test_decide_pull_gd_unreachable():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision=None, local_db_mtime=1.0) == "skip_unreachable"
```

- [ ] **Step 6.2:** Run — expect import error for `_decide_pull`.

```bash
cd ~/projects/blog7 && python -m pytest tests/test_sync_state.py -v
```

- [ ] **Step 6.3:** Add `_decide_pull` to app.py.

```python
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
```

- [ ] **Step 6.4:** Add the download helper and the pull orchestrator.

```python
def _gd_download(file_id, dest_path):
    headers = _gd_headers()
    if not headers:
        return False
    r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers=headers, params={"alt": "media"}, timeout=60, stream=True)
    if r.status_code != 200:
        _sync_log(f"download failed: {r.status_code}")
        return False
    tmp = Path(str(dest_path) + ".tmp")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    tmp.replace(dest_path)
    return True

def _pull_db_from_gd():
    """Best-effort pull on startup. Never raises."""
    import os
    if os.environ.get("BLOG7_PULL_ON_START", "1") != "1":
        _sync_log("pull disabled by env flag")
        return
    try:
        file_id, gd_time, gd_rev = _gd_find_file()
        local_state = _read_sync_state(SYNC_STATE_PATH)
        local_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0
        decision = _decide_pull(local_state, gd_rev, local_mtime)
        _sync_log(f"pull decision: {decision}")
        if decision != "pull":
            return
        if _gd_download(file_id, DB_PATH):
            _write_sync_state(SYNC_STATE_PATH, gd_rev, gd_time,
                              DB_PATH.stat().st_mtime, _device_id())
            _sync_log("pull done")
    except Exception as e:
        _sync_log(f"pull error: {e}")
```

- [ ] **Step 6.5:** Wire into startup. Find the `app.run(...)` call near the bottom of app.py. Wrap it (or ensure it's already wrapped) in a `__main__` guard, and put the pull call inside the same guard — this way test-time `from app import ...` does NOT trigger a network pull.

```python
if __name__ == "__main__":
    try:
        _pull_db_from_gd()
    except Exception as _e:
        _sync_log(f"startup pull crashed: {_e}")
    app.run(host="0.0.0.0", port=5000)
```

If app.py already has a `__main__` guard, just add the `_pull_db_from_gd()` block above the existing `app.run(...)`. If it doesn't (the app currently calls `app.run(...)` at module level), introduce the guard now.

- [ ] **Step 6.6:** Run all tests.

```bash
cd ~/projects/blog7 && python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 6.7:** Manual integration test on laptop.

(a) Start app, verify sync.log shows either `skip_in_sync` or `pull done`.
(b) Simulate GD-newer: from another shell run `rclone touch gd:Blog7/db/blog7.db --config ~/blog7-data/secrets/rclone.conf`, then restart app. Expect `pull done` and the local DB mtime to jump.
(c) Simulate conflict: `touch ~/blog7-data/db/blog7.db` (advance local mtime past the sync-state record), then restart. Expect `pull decision: conflict` — app still runs.

- [ ] **Step 6.8:** Commit.

```bash
git -C ~/projects/blog7 add app.py tests/test_sync_state.py && git -C ~/projects/blog7 commit -m "migration: best-effort pull-on-startup with conflict detection"
```

- [ ] **CHECKPOINT:** Laptop end-to-end works. Confirm with user before cutting the phone over.

---

## Task 7: Phone cutover

**Purpose:** Deploy the refactored app.py and an initial sync-state to the phone, restart Flask, verify bidirectional sync.

**Steps:**

- [ ] **Step 7.1:** Push the updated repo to the phone via git.

Laptop:
```bash
cd ~/projects/blog7 && git push origin main
```

Phone (via SSH):
```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 'cd /sdcard/projects/blog7 && git pull'
```

- [ ] **Step 7.2:** Seed an initial sync-state on the phone so the first pull doesn't trip `skip_no_state`.

From the laptop (which just pushed a fresh DB to GD, establishing known-good state):

```bash
scp -P 8022 -i ~/.ssh/id_ed25519 ~/blog7-data/db/blog7.db.sync-state.json u0_a552@10.0.0.53:/sdcard/Android/data/com.termux/files/blog7/db/blog7.db.sync-state.json
```

Then edit the `device` field on the phone to say `"phone"`:

```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 "sed -i 's/\"device\": \"laptop\"/\"device\": \"phone\"/' /sdcard/Android/data/com.termux/files/blog7/db/blog7.db.sync-state.json"
```

Also make sure the phone's `local_mtime` in the sync-state matches the phone's current DB mtime, otherwise first startup will trip `conflict`:

```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 '
MTIME=$(stat -c %Y /sdcard/Android/data/com.termux/files/blog7/db/blog7.db)
python -c "
import json, sys
p = \"/sdcard/Android/data/com.termux/files/blog7/db/blog7.db.sync-state.json\"
d = json.load(open(p))
d[\"local_mtime\"] = float($MTIME)
open(p, \"w\").write(json.dumps(d, indent=2))
"'
```

- [ ] **Step 7.3:** Restart Flask on the phone.

```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 '
pkill -f "python app.py" 2>/dev/null
cd /sdcard/projects/blog7
nohup python app.py > ~/flask.log 2>&1 &
sleep 3
tail -20 ~/flask.log
'
```
Expected: Flask startup lines, no traceback, `sync.log` updated with a pull decision.

- [ ] **Step 7.4:** Browser test — open the phone's app, poke around, hit "Save & Sync".

User-side manual step: confirm the UI works and `/exit` reports success.

- [ ] **Step 7.5:** Bidirectional verification.

(a) On laptop: `cd ~/projects/blog7 && python app.py`, visit the app, make a trivial edit (e.g. tweak a comment on a txn), Save & Sync.
(b) On phone: restart Flask (Step 7.3 block). Expect `pull done` in `/sdcard/Android/data/com.termux/files/blog7/sync.log`.
(c) On phone browser: verify the laptop's edit is visible.
(d) Reverse: edit something on phone, Save & Sync. On laptop: restart app, verify phone's edit visible.

- [ ] **Step 7.6:** Commit (laptop).

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: task 7 complete — phone cutover verified"
```

---

## Task 8: Statements sync scripts + README

**Purpose:** Document and wrap the rclone commands for cold data.

**Files:**
- Create: `~/blog7-data/README.md`
- Create: `~/blog7-data/sync_statements_push.sh`
- Create: `~/blog7-data/sync_statements_recover.sh`

**Steps:**

- [ ] **Step 8.1:** Write the push script.

`~/blog7-data/sync_statements_push.sh`:

```bash
#!/usr/bin/env bash
# Push local statements tree to Google Drive. One-way.
set -euo pipefail
DATA=~/blog7-data
rclone --config "$DATA/secrets/rclone.conf" sync \
    "$DATA/statements" gd:Blog7/statements \
    --progress
```

```bash
chmod +x ~/blog7-data/sync_statements_push.sh
```

- [ ] **Step 8.2:** Write the recover script.

`~/blog7-data/sync_statements_recover.sh`:

```bash
#!/usr/bin/env bash
# Pull statements tree from Google Drive to local. Run on a fresh laptop.
set -euo pipefail
DATA=~/blog7-data
mkdir -p "$DATA/statements"
rclone --config "$DATA/secrets/rclone.conf" sync \
    gd:Blog7/statements "$DATA/statements" \
    --progress
```

```bash
chmod +x ~/blog7-data/sync_statements_recover.sh
```

- [ ] **Step 8.3:** Write the README.

`~/blog7-data/README.md`:

```markdown
# blog7 data root

Working copy of blog7's data. Authoritative copy lives on Google Drive
under `Blog7/`. See `docs/superpowers/specs/2026-04-18-gdrive-data-migration-design.md`
in the blog7 repo for the full design.

## Contents

- `db/blog7.db` — master DB (hot; synced by the Flask app)
- `db/blog7.db.sync-state.json` — sync sidecar (do not edit by hand)
- `db/finance.db` — secondary DB (cold; push with the rclone commands below)
- `statements/` — archival PDFs and parsed outputs (cold)
- `secrets/` — runtime credentials (local-only; recovery copy on GD)
- `sync.log` — app-written sync log

## Cold-data commands

Push local statements to GD (after adding new PDFs or regenerating parses):

    ./sync_statements_push.sh

Recover statements from GD (fresh laptop setup):

    ./sync_statements_recover.sh

Push finance.db to GD (after regeneration):

    rclone --config secrets/rclone.conf copy db/finance.db gd:Blog7/db/

## Secrets recovery

A recovery copy of `secrets/*` exists on GD under `Blog7/secrets/`. To
restore on a new machine:

    mkdir -p ~/blog7-data/secrets
    rclone --config /path/to/saved/rclone.conf copy gd:Blog7/secrets ~/blog7-data/secrets
```

- [ ] **Step 8.4:** Test the push script runs cleanly (no-op expected since Task 2 already synced).

```bash
~/blog7-data/sync_statements_push.sh
```
Expected: "Transferred: 0 B" or similar.

- [ ] **Step 8.5:** Commit (since these live outside the repo, just the plan checkbox update).

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: statements sync scripts + ~/blog7-data/README.md in place"
```

---

## Task 9: Parser path update

**Purpose:** Update `~/projects/finance/` parsers to read from `~/blog7-data/statements/` instead of the old in-tree location.

**Files:**
- Modify: `~/projects/finance/Statement.py`, `~/projects/finance/de_parser.py`, `~/projects/finance/ebt_parser.py`, and any other scripts whose path constants point at `statements/`.

**Steps:**

- [ ] **Step 9.1:** Find all references.

```bash
cd ~/projects/finance && grep -rln --include='*.py' --include='*.bat' 'statements' .
```

- [ ] **Step 9.2:** For each file that hardcodes a statements path, change the constant. Prefer a single canonical form:

```python
STATEMENTS = Path.home() / "blog7-data" / "statements"
```

Keep the symlink from Task 3.6 as a safety net, but update the constants so the code is forward-looking.

- [ ] **Step 9.3:** Also update any references to `~/projects/finance/blog7.db`, `finance.db`, or `rclone.conf` in the parser scripts to `~/blog7-data/...` equivalents.

- [ ] **Step 9.4:** Smoke-test the most commonly-run parser (user: identify which one you actually use most — likely `Statement.py` or `do_all.py`). Run it against one sample statement and confirm it still succeeds.

- [ ] **Step 9.5:** Commit (finance repo, if any; otherwise just marker commit in blog7).

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: finance/ parsers pointed at ~/blog7-data/statements/"
```

---

## Task 10: Decommission old paths

**Purpose:** Remove the Task 3.6 transition symlinks and the stale DB copies under `~/projects/finance/`. Only run after several clean cycles have confirmed everything works.

**Pre-condition:** At least 3 days / 3 sync cycles of clean operation since Task 7 checkpoint. User explicitly approves.

**Steps:**

- [ ] **Step 10.1:** Verify nothing under `~/projects/finance/` is still referenced in a way that matters.

```bash
cd ~/projects/blog7 && grep -rn 'projects/finance' --include='*.py' .
```
Expected: zero hits (or only doc/comment references).

- [ ] **Step 10.2:** Remove symlinks.

```bash
rm ~/projects/finance/blog7.db
rm ~/projects/finance/blog7_backup.db
rm ~/projects/finance/finance.db
rm ~/projects/finance/statements
rm ~/projects/finance/rclone.conf
rm ~/projects/finance/ns_token.txt
rm ~/projects/finance/ns_token_laptop.txt
rm ~/projects/finance/ns_creds.txt
rm ~/projects/finance/blog7_sync.log
```

- [ ] **Step 10.3:** Run the app one more time to confirm nothing broke.

```bash
cd ~/projects/blog7 && python app.py &
sleep 3
curl -s http://localhost:5000/ | head -5
kill %1
```

- [ ] **Step 10.4:** Final commit.

```bash
git -C ~/projects/blog7 commit --allow-empty -m "migration: complete — decommissioned transition symlinks"
```

- [ ] **Step 10.5:** Update CLAUDE.md.

Replace the "File paths" table in CLAUDE.md with the new DATA_ROOT shape. Replace the "Google Drive sync" section with a pointer to the design doc.

- [ ] **Step 10.6:** Remove the migration backup once everything is stable (optional; user's call).

```bash
# Only after user explicit approval:
# rm -rf ~/blog7-migration-backup-2026-04-18
```

---

## Session-break protocol

If a session is about to end mid-plan:

1. Commit all pending changes (even WIP, as `migration: WIP task N step M`).
2. Update this plan file's checkboxes to reflect completed steps.
3. Write a memory entry `project_gdrive_migration_progress.md` with: current task number, current step, any surprises encountered, any commands that were attempted and failed.
4. Commit the memory update.

To resume in a fresh session, read:
- The spec (`docs/superpowers/specs/2026-04-18-gdrive-data-migration-design.md`)
- This plan
- The progress memory
- Then pick up at the first unchecked step.
