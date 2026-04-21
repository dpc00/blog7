from pathlib import Path
import importlib.util


def load_app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    app_path = Path(r"C:/Users/donal/projects/blog7/app.py")
    spec = importlib.util.spec_from_file_location("blog7_app_ebt_test", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_ebt_rows_replaces_existing_quest_transactions_and_updates_balance(monkeypatch):
    temp_home = Path(r"C:/Users/donal/projects/finance/finance/ebt-test-home")
    db_path = temp_home / "data" / "finance" / "db" / "blog7.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    mod = load_app_module(temp_home, monkeypatch)
    quest_id = 3

    mod.db.execute(
        "INSERT INTO transactions (id, asset_id, day, amt, flow, balance, desc, expense) VALUES (?,?,?,?,?,?,?,?)",
        ["old-ebt", quest_id, "2026-04-01", -5.0, 2, 40.0, "old", -5.0],
    )

    rows = [
        {
            "id": "ebt-1",
            "date": "04-18-2026",
            "amount_cents": 1234,
            "credit": False,
            "merchant_name": "KING SOOPERS",
            "ttype_raw": "Purchase",
        },
        {
            "id": "ebt-2",
            "date": "04-19-2026",
            "amount_cents": 10900,
            "credit": True,
            "merchant_name": None,
            "ttype_raw": "Benefit Deposit",
        },
    ]

    count, balance = mod._ebt_import_rows(rows, final_balance=86.66)

    txns = mod.db.fetchall(
        "SELECT id, day, amt, flow, desc, income, expense FROM transactions WHERE asset_id=? ORDER BY day, id",
        [quest_id],
    )
    asset = mod.db.fetchone("SELECT current_balance FROM asset WHERE asset_id=?", [quest_id])

    assert count == 2
    assert round(balance, 2) == 86.66
    assert [r.id for r in txns] == ["ebt-1", "ebt-2"]
    assert txns[0].day == "2026-04-18"
    assert txns[0].amt == -12.34
    assert txns[0].flow == 2
    assert "KING SOOPERS" in txns[0].desc
    assert txns[0].expense == 12.34
    assert txns[1].amt == 109.0
    assert txns[1].flow == 1
    assert txns[1].income == 109.0
    assert round(asset.current_balance, 2) == 86.66


def test_import_ebt_csv_uses_existing_parser(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)
    csv_path = tmp_path / "ebt.csv"
    csv_path.write_text(
        "Transaction Type,Transaction Date & Time,Store Name & Address,Transaction Amount\n"
        "Purchase,\"April 18, 2026 01:23 PM\",\"KING SOOPERS, 123 MAIN  BOULDER CO\",\"-$12.34\"\n",
        encoding="utf-8",
    )

    called = {}

    def fake_import(rows, final_balance=None):
        called["rows"] = rows
        called["final_balance"] = final_balance
        return 1, final_balance

    mod._ebt_import_rows = fake_import

    count, balance = mod._ebt_import_csv(csv_path, final_balance=44.55)

    assert count == 1
    assert round(balance, 2) == 44.55
    assert called["rows"][0]["merchant_name"] == "KING SOOPERS"
    assert called["rows"][0]["credit"] is False


def test_import_ebt_csv_skips_rows_marked_rejected_by_rejection_file(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)
    csv_path = tmp_path / "ebt.csv"
    rejection_path = tmp_path / "rejections.json"

    csv_path.write_text(
        "Transaction Type,Transaction Date & Time,Store Name & Address,Transaction Amount\n"
        "Food Purchase,\"April 17, 2026 09:36 PM MT\",\"Dashmart, 303 2nd St Ste 800     San Franciscoca Us,. E.Mode: INT\",-$ 18.21\n"
        "BENEFIT AVAIL (Food),\"April 08, 2026 12:00 AM MT\",\", ,\",$ 118.00\n",
        encoding="utf-8",
    )

    rejection_path.write_text(
        '[{"type":"Food Purchase","datetime":"April 17, 2026 09:36 PM","amount":"$18.21"}]',
        encoding="utf-8",
    )

    count, balance = mod._ebt_import_csv(csv_path, final_balance=44.55, rejection_path=rejection_path)
    txns = mod.db.fetchall(
        "SELECT id, desc, amt, flow FROM transactions WHERE asset_id=? ORDER BY day, id",
        [3],
    )

    assert count == 1
    assert round(balance, 2) == 44.55
    assert len(txns) == 1
    assert "BENEFIT AVAIL" in txns[0].desc
