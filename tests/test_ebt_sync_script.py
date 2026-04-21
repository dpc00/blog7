from pathlib import Path
import importlib.util
import time


def load_script_module():
    script_path = Path(r"C:/Users/donal/projects/blog7/scripts/ebt_sync_playwright.py")
    spec = importlib.util.spec_from_file_location("blog7_ebt_sync_script_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pick_latest_csv_returns_newest_csv(tmp_path):
    mod = load_script_module()

    older_csv = tmp_path / "older.csv"
    newer_csv = tmp_path / "newer.csv"

    older_csv.write_text("a\n", encoding="utf-8")
    time.sleep(0.05)
    newer_csv.write_text("b\n", encoding="utf-8")

    latest = mod._pick_latest_csv(tmp_path)

    assert latest == newer_csv


def test_pick_latest_rejections_returns_newest_rejection_file(tmp_path):
    mod = load_script_module()

    older_json = tmp_path / "rejections-older.json"
    newer_json = tmp_path / "rejections-newer.json"

    older_json.write_text("[]", encoding="utf-8")
    time.sleep(0.05)
    newer_json.write_text("[]", encoding="utf-8")

    latest = mod._pick_latest_rejections(tmp_path)

    assert latest == newer_json


def test_pick_sync_files_prefers_files_matching_newest_csv_stamp(tmp_path):
    mod = load_script_module()

    csv_path = tmp_path / "TransHistory20260418041343818.csv"
    pdf_match = tmp_path / "TransHistory20260418041343818.pdf"
    txt_match = tmp_path / "TransHistory20260418041343818.txt"
    rejection_match = tmp_path / "rejections-20260418041343.json"

    pdf_newer_but_unrelated = tmp_path / "TransHistory20260418041658267.pdf"
    txt_newer_but_unrelated = tmp_path / "TransHistory20260418041658267.txt"
    rejection_newer_but_unrelated = tmp_path / "rejections-20260418041658.json"

    csv_path.write_text("csv\n", encoding="utf-8")
    time.sleep(0.05)
    pdf_match.write_text("pdf match\n", encoding="utf-8")
    time.sleep(0.05)
    txt_match.write_text("txt match\n", encoding="utf-8")
    time.sleep(0.05)
    rejection_match.write_text("[]", encoding="utf-8")
    time.sleep(0.05)
    pdf_newer_but_unrelated.write_text("pdf newer\n", encoding="utf-8")
    time.sleep(0.05)
    txt_newer_but_unrelated.write_text("txt newer\n", encoding="utf-8")
    time.sleep(0.05)
    rejection_newer_but_unrelated.write_text("[]", encoding="utf-8")

    sync_files = mod._pick_sync_files(tmp_path)

    assert sync_files["csv_path"] == csv_path
    assert sync_files["pdf_path"] == pdf_match
    assert sync_files["txt_path"] == txt_match
    assert sync_files["rejections_path"] == rejection_match


def test_extract_food_balance_from_txt_reads_food_balance(tmp_path):
    mod = load_script_module()
    txt_path = tmp_path / "TransHistory20260418041658267.txt"
    txt_path.write_text(
        "Account Information\n"
        "Cash:\n"
        "Food:\n"
        "$0.00\n"
        "$0.21\n",
        encoding="utf-8",
    )

    balance = mod._extract_food_balance_from_txt(txt_path)

    assert round(balance, 2) == 0.21


def test_pick_sync_files_can_be_reported_as_found_flags(tmp_path):
    mod = load_script_module()

    csv_path = tmp_path / "TransHistory20260418041343818.csv"
    txt_path = tmp_path / "TransHistory20260418041343818.txt"

    csv_path.write_text("csv\n", encoding="utf-8")
    txt_path.write_text("txt\n", encoding="utf-8")

    sync_files = mod._pick_sync_files(tmp_path)
    files_found = {
        "csv": bool(sync_files["csv_path"]),
        "rejections": bool(sync_files["rejections_path"]),
        "pdf": bool(sync_files["pdf_path"]),
        "txt": bool(sync_files["txt_path"]),
    }

    assert files_found == {
        "csv": True,
        "rejections": False,
        "pdf": False,
        "txt": True,
    }


def test_copy_latest_downloaded_csv_copies_new_csv_into_output_folder(tmp_path, monkeypatch):
    mod = load_script_module()

    downloads_dir = tmp_path / "downloads"
    out_dir = tmp_path / "out"
    downloads_dir.mkdir()
    out_dir.mkdir()

    newer_csv = downloads_dir / "TransHistory20260419050000000.csv"
    newer_csv.write_text("csv\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_list_candidate_csvs", lambda: [newer_csv])

    copied = mod._copy_latest_downloaded_csv(out_dir, before_files=set())

    assert copied == out_dir / newer_csv.name
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == "csv\n"


def test_copy_latest_downloaded_csv_ignores_old_names_when_new_one_exists(tmp_path, monkeypatch):
    mod = load_script_module()

    downloads_dir = tmp_path / "downloads"
    out_dir = tmp_path / "out"
    downloads_dir.mkdir()
    out_dir.mkdir()

    old_csv = downloads_dir / "TransHistory20260418041343818.csv"
    new_csv = downloads_dir / "TransHistory20260419060000000.csv"
    old_csv.write_text("old\n", encoding="utf-8")
    time.sleep(0.05)
    new_csv.write_text("new\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_list_candidate_csvs", lambda: [old_csv, new_csv])

    copied = mod._copy_latest_downloaded_csv(out_dir, before_files={old_csv.name})

    assert copied == out_dir / new_csv.name
    assert copied.read_text(encoding="utf-8") == "new\n"


def test_return_to_blog7_opens_local_app_url(monkeypatch):
    mod = load_script_module()
    calls = []

    def fake_run(cmd, timeout=60, env=None):
        calls.append((cmd, timeout, env))
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(mod, "_run", fake_run)

    mod._return_to_blog7("SERIAL123")

    assert calls == [
        (
            [
                "adb",
                "-s",
                "SERIAL123",
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                "http://10.0.0.53:5000/balances?asset=3",
                "com.android.chrome",
            ],
            30,
            None,
        )
    ]
