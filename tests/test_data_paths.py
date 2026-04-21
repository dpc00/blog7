"""Verify DATA_ROOT and derived subpaths."""
from pathlib import Path


def _path_header():
    src = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    return src.split("NS API constants")[0]


def test_laptop_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    android_root = Path("/sdcard/data/finance")
    if android_root.exists():
        import pytest
        pytest.skip("running on android")

    header = _path_header()
    ns = {"__file__": str(Path(__file__).parent.parent / "app.py"), "__name__": "__main__"}
    exec(header, ns)

    assert ns["DATA_ROOT"] == tmp_path / "data" / "finance"
    assert ns["SECRETS_ROOT"] == tmp_path / "secrets" / "finance"
    assert ns["DB_PATH"] == tmp_path / "data/finance/db/blog7.db"
    assert ns["DB_BAK"] == tmp_path / "data/finance/db/blog7_backup.db"
    assert ns["RCLONE_CONF"] == tmp_path / "secrets/finance/rclone.conf"
    assert ns["TOKEN_FILE"] == tmp_path / "secrets/finance/ns_token.txt"
    assert ns["CREDS_FILE"] == tmp_path / "secrets/finance/ns_creds.txt"
    assert ns["SYNC_LOG"] == tmp_path / "data/finance/sync.log"
    assert ns["SYNC_STATE_PATH"] == tmp_path / "data/finance/db/blog7.db.sync-state.json"


def test_android_data_and_secrets_roots():
    header = _path_header()
    ns = {"__file__": str(Path(__file__).parent.parent / "app.py"), "__name__": "__main__"}

    orig_exists = Path.exists
    try:
        Path.exists = lambda self: str(self).replace("\\", "/") == "/sdcard/data/finance" or orig_exists(self)
        exec(header, ns)
    finally:
        Path.exists = orig_exists

    assert ns["ANDROID"] is True
    assert ns["DATA_ROOT"] == Path("/sdcard/data/finance")
    assert ns["SECRETS_ROOT"] == Path("/sdcard/secrets/finance")
    assert ns["TOKEN_FILE"] == Path("/sdcard/secrets/finance/ns_token.txt")
    assert ns["CREDS_FILE"] == Path("/sdcard/secrets/finance/ns_creds.txt")
    assert ns["EBT_CREDS_FILE"] == Path("/sdcard/secrets/finance/ebt_creds.json")
    assert ns["RCLONE_CONF"] == Path("/sdcard/secrets/finance/rclone.conf")
