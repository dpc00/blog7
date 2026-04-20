# 2026-04-19 EBT Progress Log

This note is here so the recent EBT work is recorded inside the repo.

## Goal

Add EBT update/sync work to `blog7` in a way that fits the phone app.

## What Was Added

### In `app.py`

- Added `_EBT_ASSET_ID = 3`
- Added `_ebt_desc(row)`
- Added `_ebt_import_rows(rows, final_balance=None)`
- Added `_load_ebt_parser()`
- Added `_ebt_import_csv(csv_path, final_balance=None)`
- Added `_ebt_run_sync_script()`
- Added `_ebt_do_sync()`
- Added Flask route `POST /sync_ebt`

### In `scripts/ebt_sync_playwright.py`

- Added a phone-side helper script for Termux
- Script launches Chrome to the EBT site
- Script uses `adb forward tcp:9222 localabstract:chrome_devtools_remote`
- Script uses Node + Playwright to attach to phone Chrome over CDP
- Script saves `state.json`
- Script saves `ebtedge-home.html`
- Script now knows the real login field selectors
- Script now reads `EBT_USER_ID` and `EBT_PASSWORD` from environment variables
- Script now fills the login form and clicks the login button when credentials are present
- Script now returns `login_attempted` in its JSON result
- Script now returns the newest CSV already present in the EBT output folder

### In `scripts/ebt_csv_parser.py`

- Added a local EBT CSV parser inside `blog7`
- This removes the earlier dependency on `~/projects/finance/finance/ebt_parser.py`
- Added support for EBT rejection JSON files

## Rejection Handling

- `blog7` now understands `rejections-*.json` files saved in the EBT folder
- rejected purchase rows are now filtered out instead of being imported as live transactions
- the phone-side EBT helper now returns the newest rejection JSON path along with the newest CSV path
- the phone-side EBT helper now groups files by the timestamp in their filenames so related CSV/PDF/TXT/rejection files stay together
- the phone-side EBT helper now reads the Food balance from the TXT sidecar and returns it as `final_balance`
- if EBT sync has a real balance but no CSV yet, `blog7` now updates the Colorado Quest balance anyway instead of failing
- the phone-side EBT helper now reports which EBT sidecar files were actually found in the folder

### In tests

- Added `tests/test_ebt_import.py`
- Added `tests/test_ebt_sync_route.py`
- Added `tests/test_ebt_sync_script.py`

### In `templates/balances.html`

- Added a visible `Sync EBT` button that posts to `/sync_ebt`

## What Was Verified

- Focused EBT tests passed after the recent script change
- Command used:

```powershell
pytest -p no:cacheprovider C:\Users\donal\projects\blog7\tests\test_ebt_sync_route.py C:\Users\donal\projects\blog7\tests\test_ebt_import.py -q --basetemp C:\Users\donal\projects\finance\finance\.pytest-tmp-ebt-continue
```

- Result: `5 passed`

## Important Facts

- `.gitignore` did not exist in `blog7` and has now been added
- No commit or push was done during this work
- The EBT path is still incomplete

## Still Missing

- Post-login navigation
- Transaction/history page capture
- CSV, HTML, or other extract import into `blog7.db`

## Readability Rule For Future Work

The user asked that new code stay readable by a beginner.

That means:

- prefer simple code over clever code
- add comments freely
- split harder logic into separate files when needed
- document new or AI-added code clearly
