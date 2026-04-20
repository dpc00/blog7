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
- the phone-side EBT helper now attempts post-login navigation to `Transactions`
- it now tries to open the `Download` flow, request `CSV`, and copy a downloaded `TransHistory*.csv` file into the EBT output folder

### In tests

- Added `tests/test_ebt_import.py`
- Added `tests/test_ebt_sync_route.py`
- Added `tests/test_ebt_sync_script.py`

### In `templates/balances.html`

- Added a visible `Sync EBT` button that posts to `/sync_ebt`

## What Was Verified

- Focused EBT route + script tests passed after the latest post-login navigation groundwork
- Command used:

```powershell
pytest -p no:cacheprovider C:\Users\donal\projects\blog7\tests\test_ebt_sync_route.py C:\Users\donal\projects\blog7\tests\test_ebt_sync_script.py -q --basetemp C:\Users\donal\projects\finance\finance\.pytest-tmp-ebt-task5
```

- Result: `13 passed`

## Important Facts

- `.gitignore` did not exist in `blog7` and has now been added
- The EBT path is still incomplete

## Current Script State

File:

- `C:\Users\donal\projects\blog7\scripts\ebt_sync_playwright.py`

What it can do now:

- launch Chrome to `https://cardholder.ebtedge.com/`
- forward DevTools with `adb forward tcp:9222 localabstract:chrome_devtools_remote`
- attach to phone Chrome with Node + Playwright over CDP
- fill the login form using:
  - `#idp-first-time-login-loginname`
  - `#idp-first-time-login-password`
  - `#idp-first-time-login-signin`
- fall back to DOM click if Playwright click is blocked
- send Android `Back` automatically for a short time to try to dismiss the Chrome saved-password popup
- try to click `Transactions`
- try to click `Download`
- try to choose `CSV`
- try to copy a downloaded `TransHistory*.csv` file from common phone download folders into the EBT output folder
- group sidecar files by timestamp
- read `final_balance` from the TXT sidecar

What it cannot do yet:

- prove the post-login page navigation is correct end-to-end
- prove the CSV download click path is correct end-to-end
- reliably inspect the live post-login DOM on the current Windows run

## Current Blocker

The script is stuck at the post-login inspection stage.

Specific things seen:

- one authenticated run failed on the login click because overlapping mobile layout elements intercepted the pointer
- that was patched with a DOM-click fallback
- after that, the Windows-side CDP inspection path became unreliable
- one run failed with:
  - `No existing Chrome tab was available for EBT automation.`
- another direct probe of:
  - `http://127.0.0.1:9222/json`
  - `http://127.0.0.1:9222/json/version`
  hung on Windows

So the next concrete step is:

- get one clean post-login DOM snapshot after successful login
- specifically inspect the live page after the `Transactions` click
- confirm the real selector or text for the download flow

Best current candidate selectors/text already wired in:

- `Transactions`
- `Posted Transactions`
- `Download`
- `Select File Type`
- `ion-option[value="csv"]`
- `option[value="csv"]`

The exact next question is:

- after login succeeds, does the page really expose `Transactions` and `Download` in the same tab and with those labels, or is there a different button/dialog path?

## Credentials / Env Vars

The script expects:

- `EBT_USER_ID`
- `EBT_PASSWORD`

The Flask wrapper in `app.py` also looks for:

- `C:\Users\donal\blog7-data\secrets\ebt_creds.json`

Expected JSON shape:

```json
{
  "user_id": "donaldchitester",
  "password": "Arckrc00!"
}
```

During this session, authenticated runs were done by setting:

- `EBT_USER_ID=donaldchitester`
- `EBT_PASSWORD=Arckrc00!`

## Current Test Status

Passing:

- `tests/test_ebt_sync_route.py`
  - route behavior
  - balance-only behavior
  - no-CSV message behavior
- `tests/test_ebt_sync_script.py`
  - file grouping
  - rejection file grouping
  - TXT balance extraction
  - CSV copy helper logic

Last clean focused pass:

```powershell
pytest -p no:cacheprovider C:\Users\donal\projects\blog7\tests\test_ebt_sync_route.py C:\Users\donal\projects\blog7\tests\test_ebt_sync_script.py -q --basetemp C:\Users\donal\projects\finance\finance\.pytest-tmp-ebt-task5
```

Result:

- `13 passed`

Known test problem:

- broader pytest runs are hitting a Windows temp-folder permission problem in `pytest-of-donal`
- that is an environment issue, not a known EBT logic regression

Recent local commits:

- `4e56539` `Add phone-side EBT sync groundwork`
- `e893f74` `Refine EBT sync status handling`
- `724fff3` `Add EBT post-login navigation groundwork`

## Session 2026-04-19 (second sitting) — What Was Learned

### Source files analyzed

Three untracked files in the repo root were downloaded from the live ebtEDGE site in a
previous session and contain the app's static assets:

- `tmp-ebtedge-index.html` — the Ionic SPA shell (no useful DOM; everything is JS-rendered)
- `tmp-ebtedge-en.json` — the full i18n string table for the app
- `tmp-ebtedge-main.js` — the 2 MB compiled Angular/Ionic bundle

### Labels confirmed from i18n

All labels already wired into the script are correct:

| Script constant | Actual UI text |
|---|---|
| `TRANSACTIONS_LINK_TEXT` | `"Transactions"` |
| `POSTED_TRANSACTIONS_TEXT` | `"Posted Transactions"` |
| `DOWNLOAD_BUTTON_TEXT` | `"Download"` |
| `SELECT_FILE_TEXT` | `"Select File Type"` |

The download dialog is labeled `"Statements"` internally (`email-download.Email Download`)
but the button that opens it from the transactions view is `"Download"` — so the script's
button label is correct.

### Bug found in the script

The script tries to click `ion-option[value='csv']` directly:

```javascript
const csvOption = page.locator("ion-option[value='csv'], option[value='csv']");
if (await csvOption.count()) {
  await csvOption.first().click();
```

This does not work. In Ionic 3, `ion-select` opens an **Ionic Alert dialog** when clicked.
The `ion-option` elements are light-DOM children of `ion-select` and are not directly
clickable in the rendered page. The correct sequence is:

1. Click the `ion-select` element (or its label "Select File Type") to open the alert
2. In the alert that opens, click the radio button for CSV
3. Click the alert's OK/Confirm button

The compiled JS confirms the model binding: `selectDownloadFileType` is what the
`downloadStatements()` function reads — and it is bound to the `ion-select`.

### Fix needed in scripts/ebt_sync_playwright.py

Replace the current CSV-selection block (which clicks `ion-option` directly) with:

```javascript
// Open the ion-select by clicking it — Ionic 3 shows an Alert dialog
const ionSelect = page.locator('ion-select');
if (await ionSelect.count()) {
  await ionSelect.first().click();
  await page.waitForTimeout(1500);

  // The Ionic alert shows radio buttons for each option.
  // Click the one whose text contains "csv" (case-insensitive).
  const csvRadio = page.locator('.alert-radio-button').filter({ hasText: /csv/i });
  if (await csvRadio.count()) {
    await csvRadio.first().click();
    await page.waitForTimeout(500);
  }

  // Confirm the selection — Ionic alert OK button is typically the last button.
  const okButton = page.locator('.alert-button-group button').last();
  if (await okButton.count()) {
    await okButton.click();
    await page.waitForTimeout(1000);
  }
}
```

This is the one concrete code change needed before the next live test.

## Session 2026-04-19 (third sitting) — Full Flow Confirmed

### What was fixed and discovered

1. **ion-select fix applied** — `ion-option` direct click replaced with the Ionic 3 Alert dialog flow (click `ion-select` → click CSV radio → click OK).

2. **Chrome DevTools page-finding fixed** — After `browser.close()`, Chrome's CDP context shows 0 pages. Fix: force-stop Chrome before each run (`am force-stop com.android.chrome`), then wait 10s for cold start. The retry loop now specifically waits for a page at the EBT or FIS login URL (not just any page), which avoids grabbing the transient new-tab page that Chrome opens momentarily.

3. **`page.goto()` removed** — Chrome navigates itself after `am start`. The explicit `page.goto()` caused `ERR_ABORTED` + page-closed errors. Removed.

4. **Back-key dismiss loop removed** — `_dismiss_android_prompts_for_a_while` sent Android Back every 2 seconds, which closed the Chrome tab. Removed entirely.

5. **Navigation path corrected** — The real path is:
   - Home page → click `.clickable-region` (EBT card) → Account Summary
   - Account Summary → click "See More" (not "Transactions") → full transactions view
   - Full transactions view → click `#emailStatements` (button labeled "Statements", not "Download")
   - Statements dialog → `ion-select` → CSV radio → OK → download triggered

6. **`_adb_pull_latest_csv` added** — When running from the laptop (phone storage not locally accessible), pulls the latest `TransHistory*.csv` from `/storage/emulated/0/Download/` via `adb pull`.

7. **`_run` now prints stderr on failure** — Makes debugging Node driver errors visible.

### Confirmed working end-to-end

Full run output:
```json
{
  "csv_path": "...tmp-ebt-live/TransHistory20260420013104496.csv",
  "files_found": {"csv": true, ...},
  "login_attempted": true
}
```

CSV contained 21 real transactions. Tests still pass (13 passed).

### Remaining

- The "Use saved password?" Chrome prompt appears on each run — cosmetic, does not block automation
- The script still has `_dismiss_android_prompts_for_a_while` code (unused now); can be removed later
- The `before_files` tracking on the laptop always uses an empty set (phone paths not local); the adb pull always takes the latest CSV regardless of whether it's new

## Session 2026-04-19 (fourth sitting) — Phone-side sync attempt

### What changed

- `ebt_creds.json` created on phone at `/sdcard/Android/data/com.termux/files/blog7/secrets/ebt_creds.json`
- Script updated (commit `6c9afa4`): replaced CDP `Input.dispatchTouchEvent` with native in-page `TouchEvent` dispatch via `page.evaluate()`, and added `selectDownloadFileType = 'csv'` before `downloadStatements()` in the `ng.probe` path
- Phone repo pulled to `6c9afa4`
- Flask restarted on phone via SSH

### What happened

- Chrome force-stopped and relaunched to ebtEDGE ✓
- Login page shown — credentials filled and submitted ✓
- Navigation to Statements download dialog ✓
- Script completed (Flask returned 302 at 20:19:47)
- **No new CSV downloaded** — `selectDownloadFileType` still not being set via UI

### Root cause still unresolved

`enableProdMode` IS called in the bundle, so `ng.probe` is NOT available at runtime.
That means:
- The `ng.probe` path in the script always returns `false`
- The fallback is clicking `ion-popover button[size="small"]` (the Download button)
- The Download button is clicked but `selectDownloadFileType` is empty → "Please select any File Type" error

The native `TouchEvent` dispatch via `page.evaluate()` on the `ion-select .item-cover` button
also did not open the Ionic Alert dialog (ion-select alert never appeared).

### Known bundle facts

- The download endpoint is `POST /rest/download?format=<type>` (only REST endpoint in bundle)
- The POST body includes: `pendingbenelist`, `postedTranslist`, `startdate`, `language`, `cashAmt`, `foodAmt`, `ptTime`, `mtdSummaryVO`, `agency`, `sitekey` (reCAPTCHA v3 token)
- `selectDownloadFileType` guards the call — if empty, shows "Please select any File Type"
- The app detects native iOS/Android via `viewService.isNativeIosOrAndroid()` and uses a different download path on native

### Next step options

1. **Try `.click()` on the ion-select cover button** — not tried yet in the new code; Ionic 3 may listen for click as well as touch on Android Chrome
2. **Intercept the download network request via Playwright** — set up a `page.route()` handler before triggering the dialog, capture the `/rest/download` response and save as CSV
3. **Direct API call** — capture cookies after login, replay the download POST from Python (blocked by reCAPTCHA v3 token requirement)
4. **Skip download entirely** — use the already-downloaded CSV (TransHistory20260420013104496.csv, 21 transactions) and just import it manually

### Problem with running sync from phone

The user accesses Flask from Chrome on the phone. The sync script force-stops Chrome mid-request, so the Flask 302 response is never received. After sync completes, Chrome shows the EBT site and the user must manually navigate back to `http://10.0.0.53:5000`.

## Session 2026-04-19 (fifth sitting) — Phone-side sync confirmed working

### What was fixed

1. **`emulator-5554` serial accepted** — `_pick_adb_serial()` was filtering out
   entries starting with `emulator-`. When running from Termux on the phone, adb
   sees the device itself as `emulator-5554`. Removed the filter so any `device`
   entry is accepted.

2. **`page.click()` on ion-select cover** — replaced the native `TouchEvent`
   dispatch with a plain Playwright `page.click()`. The Ionic Alert dialog still
   did not open, so the JS fallback fires `ionChange` / `ionSelect` events on the
   `ion-select` element directly.

3. **`page.route()` interceptor** — added before the Statements button click.
   Captures the `/rest/download` response body and writes it to
   `outDir/TransHistory-download.csv`. This fires at the network layer so it works
   even when Chrome's OS-level file-save fails ("1 download failed" toast).

4. **Node crash tolerance** — `_run()` was replaced with a bare `subprocess.run()`
   so a non-zero Node exit no longer raises an exception. Python then checks for
   `TransHistory-download.csv` on disk (written within the last 5 minutes) as a
   fallback even when `state.json` is empty.

### Confirmed working end-to-end on phone

- Full run imported 21 EBT transactions
- Newest transaction: April 17, 2026 (balance dropped to $0.21)
- Confirmed against Propel app — data matches
- Next EBT benefit loads May 8

### Known cosmetic issue

- Chrome shows "1 download failed" toast — OS blocked the file save, but the
  `page.route()` interceptor already captured the data so nothing is lost.
- After sync, Chrome reopens to the EBT site. User must navigate back to
  `http://10.0.0.53:5000` manually.

## Readability Rule For Future Work

The user asked that new code stay readable by a beginner.

That means:

- prefer simple code over clever code
- add comments freely
- split harder logic into separate files when needed
- document new or AI-added code clearly
