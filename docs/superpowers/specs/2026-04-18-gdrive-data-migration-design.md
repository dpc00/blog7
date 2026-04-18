# blog7 — Google Drive Data Migration Design

Date: 2026-04-18

## Goal

Make Google Drive the durable vault and sync bus for all blog7 data. Move
databases and statement archives out of the project repo. Enable a
laptop-enriches → phone-consumes workflow via GD, with the phone remaining
fully usable offline.

## Device roles (unchanged, clarified)

- **Phone** — the product. Primary user-facing app: manual finance data entry,
  summary viewing. Must run regardless of network or GD reachability.
- **Laptop** — dev and data-gathering workbench. Parses statement PDFs,
  enriches the master DB, pushes results to GD. Disposable: if the laptop
  disappears the phone keeps working indefinitely.

## Data classes

- **Hot data** — `blog7.db`. Read/written during normal app use. Needs
  pull-on-start and push-on-exit semantics.
- **Cold data** — statement PDFs, parsed CSVs/JSONs, `finance.db`. Archival,
  laptop-side. One-way push to GD after changes; pull only on disaster
  recovery.
- **Credentials** — `rclone.conf`, `ns_token.txt`, `ns_creds.txt`. Must be
  local at runtime (rclone.conf is the key to GD; chicken-and-egg). A
  snapshot lives on GD as a recovery copy, separate from the runtime path.

## GD layout

```
blog7/
  db/
    blog7.db
    blog7.db.sync-state.json    # revision id + mtime + device of last push
    finance.db
  statements/
    DirectExpress-*.pdf
    netspend-statement-*.pdf
    csv/
    ebtedge/
    json/
    json_from_net/
  secrets/                      # recovery-only copy, not read at runtime
    rclone.conf
    ns_token.txt
    ns_creds.txt
```

## Local layout

**Laptop** — new data root `~/blog7-data/`:

```
~/blog7-data/
  db/blog7.db
  db/blog7.db.sync-state.json
  db/finance.db
  statements/...
  secrets/rclone.conf
  secrets/ns_token.txt
  secrets/ns_creds.txt
  sync.log
  README.md                     # documents the two rclone recovery commands
```

The repo `~/projects/blog7/` becomes code-only. `~/projects/finance/` keeps
the parser scripts (`Statement.py`, `de_parser.py`, `ebt_parser.py`, etc.)
but its data contents move to `~/blog7-data/`.

**Phone** — keep existing data root
`/sdcard/Android/data/com.termux/files/blog7/`. Add `db/` and `secrets/`
subdirectories plus the sync-state file. No move required.

## app.py refactor

Replace the scattered phone/laptop path constants (currently ~lines 40–50)
with a single `DATA_ROOT` selected at runtime and derived subpaths for
`DB_PATH`, `SYNC_STATE_PATH`, `RCLONE_CONF`, `NS_TOKEN_PATH`,
`NS_CREDS_PATH`, `SYNC_LOG_PATH`. One code path, two devices, same shape.

## Sync semantics (hot data)

All three operations run on both devices using the same logic. The
sync-state sidecar `blog7.db.sync-state.json` is how we avoid relying on
flaky GD mtimes.

### Push

Triggered by `/exit` on the phone, or by a laptop-side command after
enrichment.

1. Upload local `blog7.db` to GD.
2. Record GD's returned revision id + modifiedTime + device id into local
   and GD copies of `blog7.db.sync-state.json`.
3. Log outcome to `sync.log`.

### Pull (best-effort, on app startup)

1. Fetch GD's current revision id for `blog7.db`.
2. Compare with local `sync-state.json`:
   - **GD revision matches local last-synced revision** — GD has nothing
     new; skip.
   - **GD revision differs AND local DB mtime == sync-state mtime** (no
     local edits since last sync) — safe to pull; download, refresh
     sync-state.
   - **GD revision differs AND local DB mtime > sync-state mtime** (local
     has diverged) — **conflict**. Do not pull. Log loudly. App continues
     with local.
   - **GD unreachable / any error** — skip, continue with local, log.

### Conflict resolution

- **Phone** — always favor local. Phone is the user-facing source of truth;
  its edits must never be silently overwritten.
- **Laptop** — refuse to auto-pull; surface a conflict message. User
  manually reconciles (compares the two DBs, decides which wins) then uses
  a `--force` push flag that skips the sync-state precondition.

## Cold data

- **Statements push** — `sync_statements.py` (or a documented
  `rclone sync ~/blog7-data/statements gd:blog7/statements`) runs
  laptop-side after adding PDFs or regenerating parsed outputs. One-way.
- **Statements recover** — companion
  `rclone sync gd:blog7/statements ~/blog7-data/statements`, run manually
  on a fresh laptop. Documented in `~/blog7-data/README.md`.
- **`finance.db`** — treated like a statement artifact: pushed to GD after
  laptop-side regeneration, no auto-pull.
- No sync-state sidecar needed for cold data.

## Credentials

- Runtime reads stay at the local `secrets/` path on each device.
- One-time (and after any rotation) push of `secrets/*` to GD as recovery
  copies. Not read at runtime — only consulted if rebuilding a device.

## Rollout plan

Ordered so every step is reversible and leaves the phone app working.

1. **Inventory & backup** — snapshot both local DBs and the statements
   tree into a dated folder before touching anything.
2. **Create GD layout** — make the `blog7/{db,statements,secrets}/`
   folders via rclone; push current `blog7.db`, `finance.db`, statements,
   and a recovery copy of secrets. Read-only verification. **Checkpoint
   for user confirmation.**
3. **Laptop local reorg** — create `~/blog7-data/`, move data files out of
   `~/projects/finance/`, leave the repo as code-only. Symlink fallback
   for anything missed, so old paths still resolve during transition.
4. **Refactor app.py paths** — collapse scattered constants to `DATA_ROOT`
   + derived subpaths. Phone path unchanged; laptop path becomes
   `~/blog7-data/`. Run locally on laptop to confirm nothing broke.
5. **Push logic + sync-state sidecar** — extend `_gd_upload` to record
   revision/mtime in `blog7.db.sync-state.json` on both local and GD.
   Verify against real GD on laptop.
6. **Pull-on-startup** — best-effort, honoring conflict rules above.
   Feature-flag it so it can be disabled per-device if it misbehaves.
   Test on laptop first. **Checkpoint for user confirmation.**
7. **Phone cutover** — `adb push` updated app.py + initial sync-state to
   the phone; restart Flask. Confirm the phone pulls a laptop-authored
   change and pushes its own changes on `/exit`.
8. **Statements sync scripts** — add push/recover one-liners and
   `~/blog7-data/README.md`.
9. **Parser path update** — point `Statement.py`, `de_parser.py`,
   `ebt_parser.py`, etc. at the new statements location.
10. **Decommission old paths** — after a few clean cycles, remove the
    symlinks and stale `~/projects/finance/blog7.db` /
    `blog7_backup.db`.

## Interactions with existing pieces

- **pybackup** — unchanged; it handles only the git repo, which no longer
  contains data. If it isn't running when needed, start it manually.
- **Existing `/exit` route** — replaced by the new push logic but keeps
  the same user-visible behavior and template.
- **Existing "never auto-download" guard** (app.py:506) — removed, replaced
  by the conditional pull-on-startup described above.

## Explicit non-goals

- No two-writer merging of simultaneous DB edits. Conflicts are detected
  and surfaced, not auto-resolved.
- No real-time sync. Push is on `/exit`; pull is on startup.
- No changes to the transaction schema, routes, or UI — this migration is
  purely about where data lives and how it moves.
- No change to pybackup.
