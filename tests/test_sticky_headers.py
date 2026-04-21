"""Regression tests for wide-table sticky header behavior."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class _FakeRow(dict):
    """Dict row that also supports attribute access like sqlite Row."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _FakeDb:
    def load_assets(self):
        return [{"id": 1, "name": "Cash"}]

    def fetchall(self, query, params=None):
        if "FROM flow_types" in query:
            return [_FakeRow(flow="inc", name="Income")]
        if "FROM transactions" in query:
            return [
                _FakeRow(
                    id=1,
                    day="2026-04-18",
                    label="Paycheck",
                    asset_id=1,
                    flow="inc",
                    amt=100.0,
                    balance=200.0,
                )
            ]
        if "SELECT DISTINCT day FROM daily" in query:
            return [_FakeRow(day="2026-04-18")]
        if "FROM daily WHERE day IN" in query:
            return [
                _FakeRow(
                    day="2026-04-18",
                    asset_id=1,
                    income=100.0,
                    expense=0.0,
                    transfer_in=0.0,
                    transfer_out=0.0,
                    refund_return=0.0,
                )
            ]
        return []


def test_wide_tables_render_inside_scroll_shell(monkeypatch):
    import app as blog_app

    monkeypatch.setattr(blog_app, "db", _FakeDb())
    client = blog_app.app.test_client()

    transactions_html = client.get("/transactions").get_data(as_text=True)
    daily_html = client.get("/daily").get_data(as_text=True)
    css = Path(blog_app.app.static_folder, "style.css").read_text(encoding="utf-8")

    assert 'class="table-shell"' in transactions_html
    assert 'class="table-shell"' in daily_html
    assert ".table-shell" in css
    assert "overflow: auto;" in css
    assert "max-height: calc(100dvh" in css
