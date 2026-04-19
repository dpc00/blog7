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
