---
name: EBT Sync Status
description: Current state of the EBT sync feature — fully working end-to-end on phone as of 2026-04-19
type: project
originSessionId: 6a8b20c8-ee7e-4acb-b1c5-0447a9f76f2e
---
EBT sync via Playwright/ADB was abandoned — the approach was a dead end.

**Why:** Required ADB running under Termux on the phone to drive Playwright to access the EBTEdge site. That dependency chain was fundamentally broken and useless in practice. All EBT sync code removed from app.py in commit `b570165`.

**How to apply:** Do not attempt to revive the Playwright/ADB/EBTEdge approach. Any future EBT sync needs a completely different strategy.

## What works

- `scripts/ebt_sync_playwright.py` runs from Termux on phone
- Launches Chrome to ebtEDGE, logs in, navigates to Statements dialog
- `page.route('**/rest/download**')` interceptor captures CSV at network layer
- CSV saved to `~/blog7-data/statements/ebtedge/TransHistory-download.csv` (phone: `/sdcard/Android/data/com.termux/files/blog7/statements/ebtedge/`)
- Flask `/sync_ebt` route imports CSV into DB and updates EBT balance
- 21 transactions confirmed imported; balance $0.21 confirmed against Propel app

## Navigation path (confirmed)

1. Home → click `.clickable-region` (EBT card) → Account Summary
2. Account Summary → click "See More" → Posted Transactions view
3. Posted Transactions → click `#emailStatements` ("Statements" button)
4. Statements dialog → `ion-select` cover click → fallback: fire `ionChange`/`ionSelect` JS events
5. Download button click → `page.route()` intercepts `/rest/download` response

## Known issues / cosmetic

- Chrome shows "1 download failed" toast — OS blocked file save, but interceptor already has the data
- After sync, Chrome reopens to EBT site; user must navigate back to `http://10.0.0.53:5000` manually
- `ng.probe` unavailable (prod mode Angular) — direct component access impossible
- Ionic Alert for ion-select still doesn't open reliably; JS event fallback is the working path
- Node driver exits non-zero after sync (state.json ends up `{}`); Python tolerates this

## Key commits

- `503fdcc` — page.click() on ion-select cover + page.route() interceptor
- `4ab1c1f` — allow emulator-5554 serial (Termux sees phone as emulator)
- `3db7937` — survive Node crash after route interceptor saves CSV
- `1c97bd5` — progress log updated

## Next test opportunity

May 8, 2026 — EBT benefit loads ($118 expected based on history).
