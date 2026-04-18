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
    src = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
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
    src = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    header = src.split("# ── NS API constants")[0]
    ns = {"__file__": str(Path(__file__).parent.parent / "app.py"), "__name__": "__main__"}
    exec(header, ns)
    assert ns["DATA_ROOT"] == tmp_path / "blog7-data"
    assert ns["DB_PATH"] == tmp_path / "blog7-data/db/blog7.db"
    assert ns["DB_BAK"] == tmp_path / "blog7-data/db/blog7_backup.db"
    assert ns["RCLONE_CONF"] == tmp_path / "blog7-data/secrets/rclone.conf"
    assert ns["TOKEN_FILE"] == tmp_path / "blog7-data/secrets/ns_token.txt"
    assert ns["CREDS_FILE"] == tmp_path / "blog7-data/secrets/ns_creds.txt"
    assert ns["SYNC_LOG"] == tmp_path / "blog7-data/sync.log"
    assert ns["SYNC_STATE_PATH"] == tmp_path / "blog7-data/db/blog7.db.sync-state.json"
