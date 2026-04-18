"""Verify the sync-state sidecar helpers."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_write_sync_state(tmp_path):
    from app import _write_sync_state
    p = tmp_path / "blog7.db.sync-state.json"
    _write_sync_state(
        path=p,
        revision_id="abc123",
        gd_modified_time=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
        local_mtime=1_700_000_000.0,
        device="laptop",
    )
    data = json.loads(p.read_text())
    assert data["revision_id"] == "abc123"
    assert data["gd_modified_time"] == "2026-04-18T12:00:00+00:00"
    assert data["local_mtime"] == 1_700_000_000.0
    assert data["device"] == "laptop"


def test_read_sync_state_missing(tmp_path):
    from app import _read_sync_state
    assert _read_sync_state(tmp_path / "does-not-exist.json") is None


def test_read_sync_state_roundtrip(tmp_path):
    from app import _read_sync_state, _write_sync_state
    p = tmp_path / "ss.json"
    _write_sync_state(
        path=p, revision_id="r", gd_modified_time=datetime.now(timezone.utc),
        local_mtime=1.0, device="phone",
    )
    out = _read_sync_state(p)
    assert out["revision_id"] == "r"
    assert out["device"] == "phone"


def test_decide_pull_no_local_state():
    from app import _decide_pull
    # No local sync-state → can't tell if safe; fall back to "skip" to protect local.
    assert _decide_pull(local_state=None, gd_revision="r1",
                        local_db_mtime=1.0) == "skip_no_state"


def test_decide_pull_gd_same_as_local():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision="r1", local_db_mtime=1.0) == "skip_in_sync"


def test_decide_pull_safe_to_pull():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision="r2", local_db_mtime=1.0) == "pull"


def test_decide_pull_conflict():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    # Local db has been modified since last sync AND GD has moved.
    assert _decide_pull(state, gd_revision="r2", local_db_mtime=5.0) == "conflict"


def test_decide_pull_gd_unreachable():
    from app import _decide_pull
    state = {"revision_id": "r1", "local_mtime": 1.0}
    assert _decide_pull(state, gd_revision=None, local_db_mtime=1.0) == "skip_unreachable"
