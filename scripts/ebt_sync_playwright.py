"""Phone-side EBT sync helper.

This script is called by blog7's Flask app from Termux. It uses Termux's
own adb + node + Playwright path to attach to phone Chrome over CDP.

Current behavior:
- launches Chrome to the ebtEDGE site
- forwards Chrome DevTools through adb
- attaches with Playwright from Termux
- saves a small state snapshot under the output directory

It keeps the Flask-side JSON contract stable while the actual export/login
steps are still being filled in.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path


EBT_URL = "https://cardholder.ebtedge.com/"
LOGIN_NAME_INPUT = "#idp-first-time-login-loginname"
PASSWORD_INPUT = "#idp-first-time-login-password"
LOGIN_BUTTON = "#idp-first-time-login-signin"
TRANSACTIONS_LINK_TEXT = "Transactions"
POSTED_TRANSACTIONS_TEXT = "Posted Transactions"
DOWNLOAD_BUTTON_TEXT = "Download"
SELECT_FILE_TEXT = "Select File Type"
CSV_OPTION_VALUE = "csv"
STAMP_RE = re.compile(r"(\d{14,})")
BALANCE_BLOCK_RE = re.compile(
    r"Cash:\s*Food:\s*\$([0-9,]+\.[0-9]{2})\s*\$([0-9,]+\.[0-9]{2})",
    re.IGNORECASE | re.DOTALL,
)


def _pick_latest_csv(out_dir: Path) -> Path | None:
    # Look for any CSV exports already present in the EBT output folder.
    csv_files = list(out_dir.glob("*.csv"))

    # If nothing has been exported yet, say so with None.
    if not csv_files:
        return None

    # Return the newest CSV file by modified time.
    return max(csv_files, key=lambda path: path.stat().st_mtime)


def _list_candidate_csvs() -> list[Path]:
    """
    Look in the usual phone download folders for transaction-history CSV files.
    """
    candidates = [
        Path("/storage/emulated/0/Download"),
        Path.home() / "storage" / "downloads",
        Path.home() / "downloads",
    ]
    csv_files: list[Path] = []

    for folder in candidates:
        if not folder.exists():
            continue
        csv_files.extend(folder.glob("TransHistory*.csv"))

    return csv_files


def _copy_latest_downloaded_csv(out_dir: Path, before_files: set[str]) -> Path | None:
    """
    Copy the newest newly-downloaded CSV into the EBT output folder.

    We compare filenames seen before the browser click with filenames seen after.
    """
    current_files = _list_candidate_csvs()
    new_files = [path for path in current_files if path.name not in before_files]

    # Fall back to the newest CSV even if the filename already existed.
    if not new_files:
        new_files = current_files

    if not new_files:
        return None

    latest = max(new_files, key=lambda path: path.stat().st_mtime)
    target = out_dir / latest.name

    # Copy instead of move so we do not disturb the phone's normal Downloads area.
    shutil.copy2(latest, target)
    return target


def _pick_latest_rejections(out_dir: Path) -> Path | None:
    # Look for any saved rejection JSON files in the EBT output folder.
    rejection_files = list(out_dir.glob("rejections-*.json"))

    # If there is no rejection file, say so with None.
    if not rejection_files:
        return None

    # Return the newest rejection file by modified time.
    return max(rejection_files, key=lambda path: path.stat().st_mtime)


def _extract_stamp(path: Path) -> str:
    """
    Pull the numeric timestamp chunk out of an EBT export filename.
    """
    match = STAMP_RE.search(path.name)
    return match.group(1) if match else ""


def _pick_sync_files(out_dir: Path) -> dict[str, Path | None]:
    """
    Pick the best matching set of EBT files from the output folder.

    Rule:
    - prefer the newest CSV
    - if that CSV has a timestamp in its name, prefer matching files that
      share the same timestamp
    - if there is no timestamp match, fall back to the newest file of each type
    """
    latest_csv = _pick_latest_csv(out_dir)
    latest_rejections = _pick_latest_rejections(out_dir)
    latest_pdf = None
    latest_txt = None

    pdf_files = list(out_dir.glob("*.pdf"))
    txt_files = list(out_dir.glob("*.txt"))

    if pdf_files:
        latest_pdf = max(pdf_files, key=lambda path: path.stat().st_mtime)
    if txt_files:
        latest_txt = max(txt_files, key=lambda path: path.stat().st_mtime)

    if not latest_csv:
        return {
            "csv_path": None,
            "rejections_path": latest_rejections,
            "pdf_path": latest_pdf,
            "txt_path": latest_txt,
        }

    csv_stamp = _extract_stamp(latest_csv)

    # If the CSV filename has no embedded stamp, just use simple newest-file picks.
    if not csv_stamp:
        return {
            "csv_path": latest_csv,
            "rejections_path": latest_rejections,
            "pdf_path": latest_pdf,
            "txt_path": latest_txt,
        }

    matching_pdf = next((path for path in pdf_files if csv_stamp in path.name), None)
    matching_txt = next((path for path in txt_files if csv_stamp in path.name), None)
    matching_rejections = next(
        (path for path in out_dir.glob("rejections-*.json") if csv_stamp[:12] in path.name or csv_stamp in path.name),
        None,
    )

    return {
        "csv_path": latest_csv,
        "rejections_path": matching_rejections or latest_rejections,
        "pdf_path": matching_pdf or latest_pdf,
        "txt_path": matching_txt or latest_txt,
    }


def _extract_food_balance_from_txt(path: Path | None) -> float | None:
    """
    Read the Food balance from the text sidecar when it is available.
    """
    if not path or not path.exists():
        return None

    text = path.read_text(encoding="utf-8", errors="ignore")

    # The text export usually shows:
    #   Cash:
    #   Food:
    #   $0.00
    #   $0.21
    # In that layout, the second amount is the Food balance.
    block_match = BALANCE_BLOCK_RE.search(text)
    if block_match:
        return float(block_match.group(2).replace(",", ""))

    # Fallback: if the export layout changes, look for "Food:" and use the first
    # money line that appears immediately after it.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.lower() != "food:":
            continue
        for next_line in lines[index + 1 : index + 4]:
            if next_line.startswith("$"):
                return float(next_line.lstrip("$").replace(",", ""))

    return None


def _run(
    cmd: list[str],
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        env=env,
    )


def _pick_adb_serial() -> str:
    cp = _run(["adb", "devices"])
    serials = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and not parts[0].startswith("emulator-"):
            serials.append(parts[0])
    if not serials:
        raise RuntimeError("No authorized adb device available for Playwright attach.")
    return serials[0]


def _write_node_driver(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            Object.defineProperty(process, 'platform', {{ value: 'linux' }});
            const fs = require('fs');
            const {{ chromium }} = require('playwright');
            const ebtUserId = process.env.EBT_USER_ID || '';
            const ebtPassword = process.env.EBT_PASSWORD || '';

            (async() => {{
              // Connect to the already-running Chrome instance on the phone.
              const outDir = process.argv[2];
              const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');

              // Reuse the first existing Chrome context.
              const contexts = browser.contexts();
              const context = contexts[0];

              // Reuse an existing ebtEDGE tab if one is already open.
              let pages = context.pages();
              let page = pages.find(p => (p.url() || '').includes('ebtedge')) || pages[0];

              // If Chrome had no open page at all, create one.
              if (!page) {{
                page = await context.newPage();
              }}

              // Always go to the login page first so the script starts from a known place.
              await page.goto('{EBT_URL}', {{ waitUntil: 'domcontentloaded', timeout: 60000 }});
              await page.waitForTimeout(3000);

              // Track whether we actually tried to submit the login form.
              let loginAttempted = false;
              let transactionsOpened = false;
              let downloadOpened = false;
              let csvRequested = false;

              // Only attempt login when credentials were provided by the Flask wrapper.
              if (ebtUserId && ebtPassword) {{
                // Wait for the real login form fields we already identified.
                await page.waitForSelector('{LOGIN_NAME_INPUT}', {{ timeout: 30000 }});
                await page.waitForSelector('{PASSWORD_INPUT}', {{ timeout: 30000 }});

                // Fill the exact user id field.
                await page.fill('{LOGIN_NAME_INPUT}', ebtUserId);

                // Fill the exact password field.
                await page.fill('{PASSWORD_INPUT}', ebtPassword);

                // Click the real login button.
                await page.click('{LOGIN_BUTTON}');
                loginAttempted = true;

                // Give the site time to react before we capture state.
                await page.waitForTimeout(5000);

                // After login, try to open the Transactions page.
                const transactionsLink = page.getByText('{TRANSACTIONS_LINK_TEXT}', {{ exact: true }});
                if (await transactionsLink.count()) {{
                  await transactionsLink.first().click();
                  transactionsOpened = true;
                  await page.waitForTimeout(5000);
                }}

                // Wait for the transaction-history area if it appears.
                const postedTransactions = page.getByText('{POSTED_TRANSACTIONS_TEXT}', {{ exact: true }});
                if (await postedTransactions.count()) {{
                  await postedTransactions.first().waitFor({{ timeout: 15000 }});
                }}

                // Open the statement/download dialog if the button exists.
                const downloadButton = page.getByText('{DOWNLOAD_BUTTON_TEXT}', {{ exact: true }});
                if (await downloadButton.count()) {{
                  await downloadButton.first().click();
                  downloadOpened = true;
                  await page.waitForTimeout(3000);
                }}

                // Choose CSV in the file-type select if the select appears.
                const fileTypeLabel = page.getByText('{SELECT_FILE_TEXT}', {{ exact: true }});
                if (await fileTypeLabel.count()) {{
                  const csvOption = page.locator("ion-option[value='{CSV_OPTION_VALUE}'], option[value='{CSV_OPTION_VALUE}']");
                  if (await csvOption.count()) {{
                    await csvOption.first().click();
                    await page.waitForTimeout(1000);
                  }}
                }}

                // Click Download again inside the dialog if it is present.
                const downloadButtons = page.getByText('{DOWNLOAD_BUTTON_TEXT}', {{ exact: true }});
                if (await downloadButtons.count() > 1) {{
                  await downloadButtons.nth(1).click();
                  csvRequested = true;
                  await page.waitForTimeout(8000);
                }} else if (downloadOpened) {{
                  // Some layouts may reuse the same button instead of showing a second one.
                  csvRequested = true;
                }}
              }}

              // Refresh the page list after any navigation or login click.
              pages = context.pages();
              const pageState = [];

              // Save a plain list of visible pages so the Python side can inspect what happened.
              for (const p of pages) {{
                pageState.push({{
                  title: await p.title(),
                  url: p.url()
                }});
              }}

              // Save the current HTML snapshot for debugging on the phone.
              const htmlPath = outDir + '/ebtedge-home.html';
              fs.writeFileSync(htmlPath, await page.content(), 'utf8');

              // Return a small JSON object that the Python wrapper can store.
              const state = {{
                active_title: await page.title(),
                active_url: page.url(),
                login_attempted: loginAttempted,
                transactions_opened: transactionsOpened,
                download_opened: downloadOpened,
                csv_requested: csvRequested,
                pages: pageState,
                html_path: htmlPath,
              }};
              console.log(JSON.stringify(state));
              await browser.close();
            }})().catch(err => {{
              console.error(err && err.stack ? err.stack : String(err));
              process.exit(1);
            }});
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _node_env() -> dict[str, str]:
    env = dict(os.environ)
    candidates = [
        Path.home() / "pw-android-test" / "node_modules",
        Path(__file__).resolve().parent / "node_modules",
    ]
    for candidate in candidates:
        if candidate.exists():
            env["NODE_PATH"] = str(candidate)
            return env
    raise RuntimeError("Could not locate Playwright node_modules on the phone.")


def main() -> None:
    # The Flask wrapper passes an output directory. We keep all artifacts there.
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    # This helper only works if adb and node are already available in Termux.
    if not shutil.which("adb"):
        raise SystemExit("adb not found in PATH")
    if not shutil.which("node"):
        raise SystemExit("node not found in PATH")

    # Pick the authorized phone connection that adb can already see.
    serial = _pick_adb_serial()
    csv_files_before = {path.name for path in _list_candidate_csvs()}

    # Launch Chrome to the EBT site on the phone.
    _run(
        [
            "adb",
            "-s",
            serial,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            EBT_URL,
            "com.android.chrome",
        ]
    )
    time.sleep(5)

    # Rebuild the DevTools forward each run so Playwright has a clean port.
    subprocess.run(["adb", "-s", serial, "forward", "--remove", "tcp:9222"], capture_output=True, text=True)
    _run(["adb", "-s", serial, "forward", "tcp:9222", "localabstract:chrome_devtools_remote"])

    # Write the small Node driver that actually talks to Playwright.
    driver_path = out_dir / "playwright-phone.js"
    _write_node_driver(driver_path)

    # Run the Node driver with the same environment so it can read EBT credentials.
    cp = _run(["node", str(driver_path), str(out_dir)], timeout=120, env=_node_env())
    state = json.loads(cp.stdout)

    # If the browser likely triggered a CSV download, try to copy it into out_dir.
    copied_csv = None
    if state.get("csv_requested"):
        copied_csv = _copy_latest_downloaded_csv(out_dir, csv_files_before)

    # Save the state snapshot for later debugging on the phone.
    state_path = out_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Pick the best matching set of already-saved EBT files in the folder.
    sync_files = _pick_sync_files(out_dir)
    if copied_csv:
        sync_files["csv_path"] = copied_csv
    final_balance = _extract_food_balance_from_txt(sync_files["txt_path"])
    files_found = {
        "csv": bool(sync_files["csv_path"]),
        "rejections": bool(sync_files["rejections_path"]),
        "pdf": bool(sync_files["pdf_path"]),
        "txt": bool(sync_files["txt_path"]),
    }

    # Keep the JSON contract stable for the Flask side.
    result = {
        "csv_path": str(sync_files["csv_path"]) if sync_files["csv_path"] else "",
        "rejections_path": str(sync_files["rejections_path"]) if sync_files["rejections_path"] else "",
        "pdf_path": str(sync_files["pdf_path"]) if sync_files["pdf_path"] else "",
        "txt_path": str(sync_files["txt_path"]) if sync_files["txt_path"] else "",
        "files_found": files_found,
        "final_balance": final_balance,
        "state_path": str(state_path),
        "active_url": state.get("active_url"),
        "login_attempted": state.get("login_attempted", False),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
