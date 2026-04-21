import importlib.util
from pathlib import Path


class _CP:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _load_app_module(tmp_path, monkeypatch):
    app_path = Path(r"C:\Users\donal\projects\blog7\app.py")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    spec = importlib.util.spec_from_file_location("blog7_app_test_gd_paths", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gd_db_remote_uses_data_finance_db_path(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)
    assert app.GD_DB_REMOTE == "GD:data/finance/db/blog7.db"


def test_rclone_base_cmd_uses_config_file_when_present(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)
    app.RCLONE_CONF.parent.mkdir(parents=True, exist_ok=True)
    app.RCLONE_CONF.write_text("[GD]\ntype = drive\n")

    assert app._rclone_base_cmd() == ["rclone", "--config", str(app.RCLONE_CONF)]


def test_rclone_drive_remote_uses_configured_drive_section_name(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)
    app.RCLONE_CONF.parent.mkdir(parents=True, exist_ok=True)
    app.RCLONE_CONF.write_text("[gd]\ntype = drive\n")

    assert app._rclone_drive_remote() == "gd"


def test_rclone_remote_mtime_parses_lsjson_modtime(tmp_path, monkeypatch):
    app = _load_app_module(tmp_path, monkeypatch)
    monkeypatch.setattr(
        app,
        "_rclone_run",
        lambda args, timeout=60: _CP(
            returncode=0,
            stdout='[{"Path":"blog7.db","ModTime":"2026-04-21T01:32:54.186Z"}]',
        ),
    )
    monkeypatch.setattr(app, "_sync_log", lambda msg: None)

    dt = app._rclone_remote_mtime(app.GD_DB_REMOTE)

    assert dt.isoformat() == "2026-04-21T01:32:54.186000+00:00"
