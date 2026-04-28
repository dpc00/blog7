---
name: blog7 git conflict on phone
description: Phone blog7 is diverged from remote — needs resolution in next session
type: project
---

Phone blog7 is diverged: phone has 1 commit (`14fc291 pybak`, Apr 25) that remote doesn't, remote has 4 commits phone doesn't have.

**What happened:** pybackup ran on phone after being behind 70 commits. SSH operations during that session (stash, checkout, rm -rf) disturbed files. pybackup then committed everything in working tree including things it shouldn't have.

**Key constraint:** app.py on phone is the live running Flask app — DO NOT overwrite it without verifying it matches remote first. GD downloads may have already brought the laptop's version to the phone.

**Resolution approach:** 
- Compare app.py byte-for-byte between phone and remote before any reset
- If they match, safe to `git reset --hard origin/main` on phone
- If they differ, diff carefully — phone may have legitimate edits
- Staged changes in blog7 (TransHistory csv, test files) are likely from pybackup's SSH operations, not real edits

**Why:** AI caused this by using SSH to manipulate files directly on phone, bypassing git.
**How to apply:** Resolve carefully in a dedicated blog7 session. Do not rush.
