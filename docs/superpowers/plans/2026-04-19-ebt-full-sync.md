# EBT Full Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real full EBT sync path to `blog7` that downloads current ebtEDGE export data on the laptop and imports it into `blog7.db` for the Colorado Quest asset.

**Architecture:** Keep `blog7` simple and mirror the existing Netspend shape only at the top level: one sync entrypoint, one importer, one summary-table refresh. Use Playwright only for authenticated acquisition and export download, reuse the existing `finance/ebt_parser.py` normalization logic, and map the parsed rows into `blog7`'s simpler `transactions` table with idempotent replacement for the EBT asset.

**Tech Stack:** Python, Flask, SQLite, Playwright, existing `ebt_parser.py`, pytest

---

## File Map

- Modify: `C:/Users/donal/projects/blog7/app.py`
  Add EBT sync constants, import helpers, import/write path, and a `/sync_ebt` route.
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_import.py`
  Cover parsed-row-to-`blog7.transactions` mapping, idempotent replacement, and balance updates.
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py`
  Cover route behavior with sync success/failure using monkeypatched helpers.
- Create: `C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py`
  Laptop-only acquisition script that logs in and downloads CSV if available.
- Modify: `C:/Users/donal/projects/finance/finance/ebt_parser.py`
  Only if needed to expose a helper import surface cleanly without changing parser behavior.

### Task 1: Lock Down The Import Mapping

**Files:**
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_import.py`
- Modify: `C:/Users/donal/projects/blog7/app.py`

- [ ] **Step 1: Write the failing test for parsed EBT row import**

```python
from pathlib import Path
import importlib.util


def load_app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app_path = Path(r"C:/Users/donal/projects/blog7/app.py")
    spec = importlib.util.spec_from_file_location("blog7_app_ebt_test", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_ebt_rows_replaces_existing_quest_transactions_and_updates_balance(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)
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
    assert txns[1].amt == 109.0
    assert txns[1].flow == 1
    assert round(asset.current_balance, 2) == 86.66
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_import.py::test_import_ebt_rows_replaces_existing_quest_transactions_and_updates_balance -v`

Expected: FAIL with `AttributeError` for missing `_ebt_import_rows`

- [ ] **Step 3: Write minimal implementation in `app.py`**

```python
_EBT_ASSET_ID = 3


def _ebt_desc(row):
    merchant = row.get("merchant_name") or "EBT"
    ttype = row.get("ttype_raw") or "Transaction"
    return f"{ttype}: {merchant}"


def _ebt_import_rows(rows, final_balance=None):
    db.execute("DELETE FROM transactions WHERE asset_id=?", [_EBT_ASSET_ID])

    for row in rows:
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

    if final_balance is not None:
        db.execute(
            "UPDATE asset SET current_balance=? WHERE asset_id=?",
            [round(final_balance, 2), _EBT_ASSET_ID],
        )

    _update_summary_tables()
    return len(rows), final_balance
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_import.py::test_import_ebt_rows_replaces_existing_quest_transactions_and_updates_balance -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py tests/test_ebt_import.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: add blog7 EBT transaction importer"
```

### Task 2: Add Parser Bridge Tests

**Files:**
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_import.py`
- Modify: `C:/Users/donal/projects/blog7/app.py`

- [ ] **Step 1: Write the failing test for CSV parser bridge**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_import.py::test_import_ebt_csv_uses_existing_parser -v`

Expected: FAIL with `AttributeError` for missing `_ebt_import_csv`

- [ ] **Step 3: Write minimal implementation**

```python
def _load_ebt_parser():
    import importlib.util

    parser_path = Path.home() / "projects" / "finance" / "finance" / "ebt_parser.py"
    spec = importlib.util.spec_from_file_location("finance_ebt_parser", parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ebt_import_csv(csv_path, final_balance=None):
    parser = _load_ebt_parser()
    rows = list(parser.parse_file(csv_path))
    return _ebt_import_rows(rows, final_balance=final_balance)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_import.py::test_import_ebt_csv_uses_existing_parser -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py tests/test_ebt_import.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: bridge blog7 EBT import to finance parser"
```

### Task 3: Add Route-Level Sync Entry Point

**Files:**
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py`
- Modify: `C:/Users/donal/projects/blog7/app.py`

- [ ] **Step 1: Write the failing route test**

```python
from pathlib import Path
import importlib.util


def load_app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app_path = Path(r"C:/Users/donal/projects/blog7/app.py")
    spec = importlib.util.spec_from_file_location("blog7_app_ebt_route_test", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_ebt_route_flashes_success(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)

    def fake_sync():
        return 17, 52.25, None

    monkeypatch.setattr(mod, "_ebt_do_sync", fake_sync)
    client = mod.app.test_client()

    response = client.post("/sync_ebt", follow_redirects=True)

    assert response.status_code == 200
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("Synced EBT" in msg for _, msg in flashes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py::test_sync_ebt_route_flashes_success -v`

Expected: FAIL because `/sync_ebt` route does not exist

- [ ] **Step 3: Write minimal route implementation**

```python
def _ebt_do_sync():
    return 0, None, "EBT sync not configured."


@app.route('/sync_ebt', methods=['POST'])
def sync_ebt():
    n, bal, err = _ebt_do_sync()
    if err:
        flash(err, "err")
    else:
        bal_str = f"  bal=${bal:.2f}" if bal is not None else ""
        flash(f"Synced EBT - {n} entries{bal_str}", "ok")
    return redirect(url_for('balances', asset=_EBT_ASSET_ID))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py::test_sync_ebt_route_flashes_success -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py tests/test_ebt_sync_route.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: add EBT sync route stub"
```

### Task 4: Build The Laptop Playwright Acquisition Script

**Files:**
- Create: `C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py`
- Create: `C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py`

- [ ] **Step 1: Write the failing test for sync command contract**

```python
def test_ebt_do_sync_uses_csv_path_from_script(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)

    script_result = {
        "csv_path": str(tmp_path / "ebt.csv"),
        "final_balance": 77.77,
    }

    (tmp_path / "ebt.csv").write_text(
        "Transaction Type,Transaction Date & Time,Store Name & Address,Transaction Amount\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "_ebt_run_sync_script", lambda: script_result)
    monkeypatch.setattr(mod, "_ebt_import_csv", lambda path, final_balance=None: (5, final_balance))

    count, balance, err = mod._ebt_do_sync()

    assert (count, round(balance, 2), err) == (5, 77.77, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py::test_ebt_do_sync_uses_csv_path_from_script -v`

Expected: FAIL because `_ebt_run_sync_script` or `_ebt_do_sync` contract is missing

- [ ] **Step 3: Write the acquisition script and caller**

```python
# scripts/ebt_sync_playwright.py
import json
import sys
from pathlib import Path


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "csv_path": str(out_dir / "latest-ebt.csv"),
        "final_balance": None,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

```python
# app.py
def _ebt_run_sync_script():
    import json
    import subprocess

    out_dir = DATA_ROOT / "statements" / "ebtedge"
    script = Path(__file__).parent / "scripts" / "ebt_sync_playwright.py"
    cp = subprocess.run(
        ["python", str(script), str(out_dir)],
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    return json.loads(cp.stdout)


def _ebt_do_sync():
    try:
        result = _ebt_run_sync_script()
        csv_path = result.get("csv_path")
        if not csv_path:
            return 0, None, "EBT sync produced no CSV."
        count, balance = _ebt_import_csv(csv_path, final_balance=result.get("final_balance"))
        return count, balance, None
    except Exception as exc:
        return 0, None, f"EBT sync failed: {exc}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py::test_ebt_do_sync_uses_csv_path_from_script -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py scripts/ebt_sync_playwright.py tests/test_ebt_sync_route.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: add laptop EBT acquisition script contract"
```

### Task 5: Replace Script Stub With Real Playwright Export Logic

**Files:**
- Modify: `C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py`
- Modify: `C:/Users/donal/projects/blog7/app.py`

- [ ] **Step 1: Write the failing smoke test expectation as a manual verification note**

```text
Manual scenario:
1. Run python C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py C:/Users/donal/blog7-data/statements/ebtedge
2. Log in through Playwright-controlled browser.
3. Download CSV export from ebtEDGE statements/history page.
4. Script prints JSON containing csv_path and final_balance.
```

- [ ] **Step 2: Implement the real Playwright flow**

```python
from playwright.sync_api import sync_playwright


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto("https://cardholder.ebtedge.com/")
        # complete login/navigation using stable selectors discovered during implementation
        # capture CSV download to out_dir / "latest-ebt.csv"
        result = {
            "csv_path": str(out_dir / "latest-ebt.csv"),
            "final_balance": None,
        }
        print(json.dumps(result))
        browser.close()
```

- [ ] **Step 3: Run manual smoke verification**

Run: `python C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py C:/Users/donal/blog7-data/statements/ebtedge`

Expected: browser opens, export downloads, script prints JSON with `csv_path`

- [ ] **Step 4: Verify the end-to-end app route manually**

Run:

```bash
cd C:/Users/donal/projects/blog7
python app.py
```

Then submit the `POST /sync_ebt` action from the UI.

Expected: flash message `Synced EBT - N entries`, Colorado Quest recent transactions update, summary tables refresh.

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py scripts/ebt_sync_playwright.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: implement Playwright-based EBT full sync"
```

### Task 6: Add Failure Handling For Low-Friction Recovery

**Files:**
- Modify: `C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py`
- Modify: `C:/Users/donal/projects/blog7/app.py`

- [ ] **Step 1: Write the failing error-path test**

```python
def test_sync_ebt_route_flashes_error(tmp_path, monkeypatch):
    mod = load_app_module(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_ebt_do_sync", lambda: (0, None, "EBT sync failed: login"))
    client = mod.app.test_client()

    response = client.post("/sync_ebt", follow_redirects=True)

    assert response.status_code == 200
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("EBT sync failed: login" in msg for _, msg in flashes)
```

- [ ] **Step 2: Run test to verify it fails if error handling regresses**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py::test_sync_ebt_route_flashes_error -v`

Expected: FAIL only if route does not flash the returned error

- [ ] **Step 3: Adjust route/logging minimally if needed**

```python
def sync_ebt():
    n, bal, err = _ebt_do_sync()
    if err:
        _sync_log(err)
        flash(err, "err")
    else:
        bal_str = f"  bal=${bal:.2f}" if bal is not None else ""
        flash(f"Synced EBT - {n} entries{bal_str}", "ok")
    return redirect(url_for('balances', asset=_EBT_ASSET_ID))
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest C:/Users/donal/projects/blog7/tests/test_ebt_sync_route.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/Users/donal/projects/blog7 add app.py tests/test_ebt_sync_route.py
git -C C:/Users/donal/projects/blog7 commit -m "feat: harden EBT sync error handling"
```

## Self-Review

- Spec coverage: acquisition, parsing, import, route, and error handling are all covered.
- Placeholder scan: the only deliberately manual section is the Playwright smoke verification, because stable selectors are unknown until browser inspection.
- Type consistency: `_ebt_do_sync()` always returns `(count, balance, err)` and route/tests use the same contract.
