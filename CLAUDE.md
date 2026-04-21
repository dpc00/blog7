# blog7

Flask-based personal finance tracker. Runs on both Android phone (Termux) and Windows laptop.

## What it does

- Tracks balances across multiple payment accounts (Netspend, Direct Express, Colorado Quest EBT, Cash)
- Syncs Netspend transactions via NS API
- Backs up SQLite DB locally and pushes to Google Drive on "Save & Sync"
- Could sync EBT Food Stamps transactions using newly developed tactics from finance project

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

`app.py` picks `DATA_ROOT` at runtime: the phone path if `/sdcard/data/finance` exists, otherwise `~/data/finance/`. Secret/token paths are split from data on both platforms: `/sdcard/secrets/finance` on the phone and `~/secrets/finance` on the laptop.

| File | Phone path | Laptop path |
|------|------------|-------------|
| DB | `db/blog7.db` | `db/blog7.db` |
| DB backup | `db/blog7_backup.db` | `db/blog7_backup.db` |
| Sync-state sidecar | `db/blog7.db.sync-state.json` | `db/blog7.db.sync-state.json` |
| rclone.conf | `/sdcard/secrets/finance/rclone.conf` | `~/secrets/finance/rclone.conf` |
| NS token | `/sdcard/secrets/finance/ns_token.txt` | `~/secrets/finance/ns_token.txt` |
| NS creds | `/sdcard/secrets/finance/ns_creds.txt` | `~/secrets/finance/ns_creds.txt` |
| Sync log | `sync.log` | `sync.log` |

DATA_ROOT values:
- Phone: `/sdcard/data/finance/`
- Laptop: `~/data/finance/`

Authoritative copy of everything lives on Google Drive under `Blog7/` (see `docs/superpowers/specs/2026-04-18-gdrive-data-migration-design.md`).

## Network

- Phone IP: `10.0.0.53`
- Laptop IP: `10.0.0.56`
- Both only reachable on home WiFi (`10.0.0.x`)

## ADB (phone access from laptop without Termux)

Phone has wireless debugging enabled frequently. Pair first (code expires quickly):
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

- "Save & Sync" → `/exit` route uploads `blog7.db` to `Blog7/db/` on GD, then writes a sync-state sidecar recording GD's revision id.
- On startup, the app does a best-effort pull: if GD's revision differs from the local sync-state AND local has no unsynced edits, it downloads. Diverging edits are flagged as a conflict (phone always favors local; laptop refuses to auto-pull).
- rclone.conf section is `[gd]` (renamed from `[G]` on 2026-04-18 to avoid Windows G:\ drive-letter collision). The app filters by `type = drive`, so the section name is cosmetic for the app but matters for CLI `rclone gd:…` commands.
- Full design: `docs/superpowers/specs/2026-04-18-gdrive-data-migration-design.md`. Cold-data (statements, finance.db) sync scripts live at `~/data/finance/sync_statements_{push,recover}.sh`.
- Log: `sync.log` under DATA_ROOT.

