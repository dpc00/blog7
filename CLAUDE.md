# blog7

Flask-based personal finance tracker. Runs on both Android phone (Termux) and Windows laptop.

## What it does

- Tracks balances across multiple payment accounts (Netspend, Direct Express, Colorado Quest EBT, Cash)
- Syncs Netspend transactions via NS API
- Backs up SQLite DB locally and pushes to Google Drive on "Save & Sync"

## Running the app

### Phone (Termux)
```bash
cd /sdcard/projects/blog7
python app.py
```
this line is wrong: Access at `http://localhost:5000` on the phone browser.

### Laptop
```bash
cd ~/projects/blog7
python app.py
```
this line is wrong: Access at `http://localhost:5000` or from phone browser at `http://10.0.0.56:5000` (home WiFi only).

## File paths

Many of these paths are not correct:

| File | Phone | Laptop |
|------|-------|--------|
| DB | `/sdcard/Blog6/blog6.db` | `~/projects/finance/blog6.db` |
| DB backup | `/sdcard/Blog6/blog6_backup.db` | `~/projects/finance/blog6_backup.db` |
| rclone.conf | `/sdcard/Blog6/rclone.conf` | `~/projects/finance/rclone.conf` |
| NS token | `/sdcard/Blog6/ns_token.txt` | `~/projects/finance/ns_token_laptop.txt` |
| Sync log | `/sdcard/Blog6/sync.log` | `~/projects/finance/blog7_sync.log` |

## Network

- Phone IP: `10.0.0.53`
- Laptop IP: `10.0.0.56`
- Both only reachable on home WiFi (`10.0.0.x`)

## ADB (phone access from laptop without Termux)

Phone has wireless debugging enabled (occasionaly). Pair first (code expires quickly):
```bash
adb pair 10.0.0.53:<pairing-port> <6-digit-code>
adb connect 10.0.0.53:33551
```
Connection port is `33551` (no, that is bunk). Pairing port and code come from phone's Developer Options > Wireless Debugging > Pair device.

This may be true:
Note: ADB shell cannot kill Termux processes (permission denied). To stop Flask/sshd/crond, use Termux directly or Force Stop Termux via Settings > Apps.

## git / pybackup

- Repo: `https://github.com/dpc00/blog7`
- On phone the repo lives at `/sdcard/projects/blog7` (moved from `~/blog7`)
- On laptop the repo is at ~/projects/blog7
- pybackup auto-discovers it there and handles git push/pull automatically
- On laptop, push changes here; pybackup pulls them to the phone on its next cycle

## Google Drive sync

- "Save & Sync" button calls `/exit` route
- Only uploads if local DB is newer than GD copy
- Uses rclone.conf for OAuth token; token auto-refreshes
- If sync shows "Backed up locally", check `blog7_sync.log` — likely GD is already newer
- lot's of trouble with GD timestamps
