from pathlib import Path
import importlib.util


def load_app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    app_path = Path(r"C:/Users/donal/projects/blog7/app.py")
    spec = importlib.util.spec_from_file_location("blog7_app_ebt_route_test", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_ebt_route_flashes_success(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)

    def fake_sync():
        return 17, 52.25, None

    monkeypatch.setattr(mod, "_ebt_do_sync", fake_sync)
    client = mod.app.test_client()

    response = client.post("/sync_ebt")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("Synced EBT - 17 entries  bal=$52.25" in msg for _, msg in flashes)


def test_ebt_do_sync_uses_csv_path_from_script(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home-sync")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)

    csv_path = temp_home / "ebt.csv"
    csv_path.write_text(
        "Transaction Type,Transaction Date & Time,Store Name & Address,Transaction Amount\n",
        encoding="utf-8",
    )

    script_result = {
        "csv_path": str(csv_path),
        "final_balance": 77.77,
    }

    monkeypatch.setattr(mod, "_ebt_run_sync_script", lambda: script_result)
    monkeypatch.setattr(
        mod,
        "_ebt_import_csv",
        lambda path, final_balance=None, rejection_path=None: (5, final_balance),
    )

    count, balance, err = mod._ebt_do_sync()

    assert (count, round(balance, 2), err) == (5, 77.77, None)


def test_sync_ebt_route_flashes_error(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home-error")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)
    monkeypatch.setattr(mod, "_ebt_do_sync", lambda: (0, None, "EBT sync failed: login"))
    client = mod.app.test_client()

    response = client.post("/sync_ebt")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("EBT sync failed: login" in msg for _, msg in flashes)


def test_ebt_do_sync_updates_balance_when_only_balance_is_available(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home-balance-only")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)

    monkeypatch.setattr(
        mod,
        "_ebt_run_sync_script",
        lambda: {"csv_path": "", "final_balance": 12.34},
    )

    count, balance, err = mod._ebt_do_sync()
    asset = mod.db.fetchone("SELECT current_balance FROM asset WHERE asset_id=?", [3])

    assert (count, round(balance, 2), err) == (0, 12.34, None)
    assert round(asset.current_balance, 2) == 12.34


def test_sync_ebt_route_flashes_balance_only_message(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home-balance-flash")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)
    monkeypatch.setattr(mod, "_ebt_do_sync", lambda: (0, 12.34, None))
    client = mod.app.test_client()

    response = client.post("/sync_ebt")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("Updated EBT balance only  bal=$12.34" in msg for _, msg in flashes)


def test_ebt_do_sync_reports_found_sidecar_files_when_csv_is_missing(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-route-test-home-found-files")
    db_path = temp_home / "blog7-data" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)

    monkeypatch.setattr(
        mod,
        "_ebt_run_sync_script",
        lambda: {
            "csv_path": "",
            "final_balance": None,
            "files_found": {"csv": False, "rejections": True, "pdf": True, "txt": True},
        },
    )

    count, balance, err = mod._ebt_do_sync()

    assert count == 0
    assert balance is None
    assert err == "EBT sync found no CSV. Files found: rejections, pdf, txt"
