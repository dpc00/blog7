import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _load_app_module(tmp_path, monkeypatch):
    app_path = Path(r"C:\Users\donal\projects\blog7\app.py")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    spec = importlib.util.spec_from_file_location("blog7_app_test_exit_status", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_db_with_gd_status_reports_in_sync_when_drive_is_current(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)

    monkeypatch.setattr(app, "_rclone_remote_mtime", lambda path: datetime(2026, 4, 21, 1, 32, 54, tzinfo=timezone.utc))
    monkeypatch.setattr(app, "_sync_log", lambda msg: None)
    monkeypatch.setattr(app, "_rclone_copyto", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("copy should not run")))

    app.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.DB_PATH.write_bytes(b"db")
    ts = datetime(2026, 4, 21, 1, 28, 42, tzinfo=timezone.utc).timestamp()
    app.DB_PATH.touch()
    import os
    os.utime(app.DB_PATH, (ts, ts))

    assert app._sync_db_with_gd_status(app.DB_PATH) == "in_sync"


def test_sync_db_with_gd_status_pushes_with_rclone_when_local_is_newer(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)

    remote_time = datetime(2026, 4, 21, 1, 20, 0, tzinfo=timezone.utc)
    state_writes = []
    copy_calls = []

    monkeypatch.setattr(app, "_rclone_remote_mtime", lambda path: remote_time)
    monkeypatch.setattr(app, "_sync_log", lambda msg: None)
    monkeypatch.setattr(app, "_write_sync_state", lambda *args: state_writes.append(args))
    monkeypatch.setattr(app, "_device_id", lambda: "phone")

    def fake_copyto(src, dst):
        copy_calls.append((src, dst))
        return True

    monkeypatch.setattr(app, "_rclone_copyto", fake_copyto)

    app.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.DB_PATH.write_bytes(b"db")
    ts = datetime(2026, 4, 21, 1, 28, 42, tzinfo=timezone.utc).timestamp()
    import os
    os.utime(app.DB_PATH, (ts, ts))

    assert app._sync_db_with_gd_status(app.DB_PATH) == "pushed"
    assert copy_calls == [(app.DB_PATH, app._gd_db_remote())]
    assert state_writes
