"""
Read ebtEDGE transaction-history CSV files for blog7.

This file is intentionally plain and heavily commented.
It exists so blog7 does not depend on the separate finance repo
just to understand an EBT CSV export.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


# Match strings like:
#   -$ 16.00
#   $ 118.00
#   (Rejected) $ 12.34
AMOUNT_RE = re.compile(r"^\(?(?P<rejected>Rejected)?\)?\s*(?P<sign>-?)\$\s*(?P<number>[\d,.]+)$")

# Match the trailing entry-mode text when the export includes it.
ENTRY_MODE_RE = re.compile(r"\.\s*E\.Mode:\s*(\w+)\s*$")


def parse_amount(text: str) -> dict:
    """
    Turn the CSV amount text into cents plus a credit/debit flag.
    """
    match = AMOUNT_RE.match(text.strip())
    if not match:
        raise ValueError(f"bad amount: {text!r}")

    cents = int(round(float(match["number"].replace(",", "")) * 100))

    return {
        "cents": cents,
        "credit": match["sign"] != "-",
        "rejected": bool(match["rejected"]),
    }


def parse_merchant(text: str) -> dict:
    """
    Break the store/address field into smaller readable parts.
    """
    text = text.strip()

    # Some credit rows have an empty merchant field like ", ,".
    if text in ("", ", ,"):
        return {
            "name": None,
            "street": None,
            "locality": None,
            "entry_mode": None,
        }

    entry_mode = None
    entry_match = ENTRY_MODE_RE.search(text)

    # If the export ends with ". E.Mode: INT", pull that off first.
    if entry_match:
        entry_mode = entry_match.group(1)
        text = text[: entry_match.start()].rstrip(",. ")

    # The first comma usually separates store name from the rest.
    name, _, rest = text.partition(",")

    # The remaining text usually has large spaces between street and city/state.
    pieces = re.split(r"\s{2,}", rest.strip(), maxsplit=1)
    street = pieces[0].strip() if pieces and pieces[0] else None
    locality = pieces[1].strip() if len(pieces) > 1 else None

    return {
        "name": name.strip() or None,
        "street": street,
        "locality": locality,
        "entry_mode": entry_mode,
    }


def parse_datetime(text: str) -> datetime:
    """
    Parse the ebtEDGE date/time text.
    """
    cleaned = text.replace(" MT", "").strip()
    return datetime.strptime(cleaned, "%B %d, %Y %I:%M %p")


def transaction_id(row: dict) -> str:
    """
    Build a stable short id from the raw CSV row text.
    """
    key = (
        f"{row['Transaction Date & Time']}|"
        f"{row['Transaction Amount']}|"
        f"{row['Store Name & Address']}|"
        f"{row['Transaction Type']}"
    )
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def load_rejections(path: str | Path) -> set:
    """
    Build a lookup set for rejected transactions.

    The rejection JSON file already exists in the EBT folder when the
    earlier extraction step found rejected purchases.
    """
    keys = set()

    for row in json.loads(Path(path).read_text(encoding="utf-8")):
        when = datetime.strptime(row["datetime"], "%B %d, %Y %I:%M %p")
        cents = int(round(float(row["amount"].lstrip("$").replace(",", "")) * 100))
        keys.add((when.isoformat(), cents, row["type"]))

    return keys


def parse_file(path: str | Path, rejections: set | None = None):
    """
    Yield normalized rows from one EBT CSV file.

    The returned row shape is the shape blog7's import code expects.
    """
    rejections = rejections or set()

    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            amount = parse_amount(row["Transaction Amount"])
            when = parse_datetime(row["Transaction Date & Time"])
            merchant = parse_merchant(row["Store Name & Address"])
            rejected = amount["rejected"] or (
                when.isoformat(),
                amount["cents"],
                row["Transaction Type"],
            ) in rejections

            yield {
                "id": transaction_id(row),
                "ttype_raw": row["Transaction Type"],
                "datetime": when.isoformat(),
                "date": when.strftime("%m-%d-%Y"),
                "amount_cents": amount["cents"],
                "credit": amount["credit"],
                "rejected": rejected,
                "merchant_name": merchant["name"],
                "merchant_street": merchant["street"],
                "merchant_locality": merchant["locality"],
                "entry_mode": merchant["entry_mode"],
            }
