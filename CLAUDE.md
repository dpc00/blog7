# blog7

Flask-based personal finance tracker. Runs on both Android phone (Termux) and Windows laptop.

## What it does

- Tracks balances across multiple payment accounts (Netspend, Direct Express, Colorado Quest EBT, Cash)
- Syncs Netspend transactions via NS API
- Backs up SQLite DB locally and pushes to Google Drive on "Save & Sync"

## Running the app

App binds to `0.0.0.0:5000` (see `app.py`).

### Phone (Termux)
```bash
cd /sdcard/projects/blog7
python app.py
```
Access from phone browser at `http://10.0.0.53:5000` (home WiFi).

### Laptop
```bash
cd ~/projects/blog7
python app.py
```
Access locally at `http://localhost:5000`. Reachable from other home-WiFi devices at `http://10.0.0.56:5000` if Windows Firewall allows inbound on port 5000.

## File paths

Paths are chosen at runtime in `app.py` based on whether `/sdcard/Android/data/com.termux/files/blog7` exists.

| File | Phone | Laptop |
|------|-------|--------|
| DB | `/sdcard/Android/data/com.termux/files/blog7/blog7.db` | `~/projects/finance/blog7.db` |
| DB backup | `/sdcard/Android/data/com.termux/files/blog7/blog7_backup.db` | `~/projects/finance/blog7_backup.db` |
| rclone.conf | `/sdcard/Android/data/com.termux/files/blog7/rclone.conf` | `~/projects/finance/rclone.conf` |
| NS token | `/sdcard/Android/data/com.termux/files/blog7/ns_token.txt` | `~/projects/finance/ns_token_laptop.txt` |
| NS creds | `/sdcard/Android/data/com.termux/files/blog7/ns_creds.txt` | `~/projects/finance/ns_creds.txt` |
| Sync log | `/sdcard/Android/data/com.termux/files/blog7/sync.log` | `~/projects/finance/blog7_sync.log` |

## Network

- Phone IP: `10.0.0.53`
- Laptop IP: `10.0.0.56`
- Both only reachable on home WiFi (`10.0.0.x`)

## ADB (phone access from laptop without Termux)

Phone has wireless debugging enabled occasionally. Pair first (code expires quickly):
```bash
adb pair 10.0.0.53:<pairing-port> <6-digit-code>
adb connect 10.0.0.53:<connect-port>
```
Pairing port, connect port, and code come from the phone's Developer Options > Wireless Debugging (the connect port changes each session; don't hardcode it).

Note: ADB shell cannot (that we know of now) kill Termux processes (permission denied). To stop Flask/sshd/crond, use Termux directly or Force Stop Termux via Settings > Apps.

## git / pybackup

- Repo: `https://github.com/dpc00/blog7`
- Phone repo: `/sdcard/projects/blog7` (moved from `~/blog7`)
- Laptop repo: `~/projects/blog7`
- pybackup auto-discovers the phone repo and handles git push/pull automatically
- Workflow: push changes from laptop; pybackup pulls them to the phone on its next cycle

## Google Drive sync

- "Save & Sync" button calls `/exit` route
- Only uploads if local DB is newer than GD copy
- Uses rclone.conf for OAuth token; token auto-refreshes
- If sync shows "Backed up locally", check `blog7_sync.log` — likely GD is already newer
- Known issue: GD timestamps are flaky and have caused repeated sync headaches; when in doubt, inspect `blog7_sync.log` and compare mtimes directly
