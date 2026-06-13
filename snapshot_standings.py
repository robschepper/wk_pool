#!/usr/bin/env python3
"""
snapshot_standings.py
---------------------
Fetches the current WKPooltjes ranking widget, parses out the standings
(rank / name / points) and appends one snapshot per day to
standings-history.json. Re-running on the same day overwrites that day's
entry, so it is safe to run as often as you like.

Run locally:   python snapshot_standings.py
In CI:         see .github/workflows/snapshot-standings.yml

Configurable via environment variables (all optional):
  WIDGET_URL  full widget endpoint   (defaults to the one in your page)
  POOL_ID     label stored in the json
  REFERER     Referer header sent with the request
  OUT_FILE    output json path        (default: standings-history.json)
"""

import os
import re
import sys
import json
import datetime as dt

import requests
from bs4 import BeautifulSoup

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Brussels")
except Exception:                      # pragma: no cover
    TZ = None

WIDGET_URL = os.environ.get(
    "WIDGET_URL",
    "https://www.wkpooltjes.nl/rankingpoolwidget/b536afe31e61385d1494d8033e2f8e01/127/",
)
POOL_ID  = os.environ.get("POOL_ID", "127")
REFERER  = os.environ.get("REFERER", "https://www.wkpooltjes.nl/")
OUT_FILE = os.environ.get("OUT_FILE", "standings-history.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl,en;q=0.8",
    "Referer": REFERER,
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_html() -> str:
    resp = requests.get(WIDGET_URL, headers=HEADERS, timeout=30)
    print(f"[fetch] {WIDGET_URL} -> HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def _clean_number(text: str):
    """Turn '1.234', '12 ptn', '8,0' etc. into an int/float, or None."""
    if text is None:
        return None
    t = (text.replace("\xa0", " ")
             .replace(".", "")        # thousands separator (NL)
             .strip())
    m = re.search(r"-?\d+(?:,\d+)?", t)
    if not m:
        return None
    val = m.group(0).replace(",", ".")
    f = float(val)
    return int(f) if f.is_integer() else f


def parse_standings(html: str):
    """
    Best-effort parser. Looks for the first <table>, then for each data row
    decides which cell is the name (the longest non-numeric one) and which
    numeric cells are rank / points.

    Returns a list of {"rank", "name", "points"} dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    rows = []
    if table:
        trs = table.find_all("tr")
    else:
        # No table -> try common list/row containers as a fallback.
        trs = soup.select("li, .row, .ranking-row, [class*='rank']")

    position = 0
    for tr in trs:
        cells = tr.find_all(["td", "th"]) if table else [tr]
        texts = [c.get_text(" ", strip=True) for c in cells]
        texts = [t for t in texts if t != ""]
        if not texts:
            continue

        # Skip a header row (all cells non-numeric & short list of headers).
        numeric = [_clean_number(t) for t in texts]
        if all(n is None for n in numeric):
            continue

        # Name = longest cell that is not purely a number.
        name_candidates = [t for t, n in zip(texts, numeric)
                           if n is None and re.search(r"[A-Za-zÀ-ÿ]", t)]
        if not name_candidates:
            continue
        name = max(name_candidates, key=len)

        nums = [n for n in numeric if n is not None]
        position += 1
        # First numeric that looks like a small position -> rank, else enumerate.
        rank = None
        if nums and 1 <= nums[0] <= 200 and float(nums[0]).is_integer():
            rank = int(nums[0])
        if rank is None:
            rank = position
        # Points = the last numeric cell (usually the score column).
        points = nums[-1] if nums else None
        if points is not None and points == rank and len(nums) == 1:
            points = None  # only the rank number was present

        rows.append({"rank": rank, "name": name, "points": points})

    # Normalise: sort by rank, re-number sequentially to be safe.
    rows.sort(key=lambda r: r["rank"])
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def load_history(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"pool": POOL_ID, "updated": None, "snapshots": []}


def main():
    html = fetch_html()
    standings = parse_standings(html)

    if not standings:
        # Save raw HTML so you can inspect the structure and adjust the parser.
        with open("debug_widget.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("[warn] No standings parsed. Raw HTML saved to debug_widget.html.")
        print("[warn] Share that file's table structure and the parser can be tuned.")
        sys.exit(1)

    now = dt.datetime.now(TZ) if TZ else dt.datetime.now()
    today = now.strftime("%Y-%m-%d")

    history = load_history(OUT_FILE)
    history["pool"] = POOL_ID
    history["updated"] = now.isoformat(timespec="seconds")

    snaps = [s for s in history.get("snapshots", []) if s.get("date") != today]
    snaps.append({
        "date": today,
        "captured_at": now.isoformat(timespec="seconds"),
        "standings": standings,
    })
    snaps.sort(key=lambda s: s["date"])
    history["snapshots"] = snaps

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"[ok] {today}: captured {len(standings)} players "
          f"(leader: {standings[0]['name']}). Total snapshots: {len(snaps)}.")


if __name__ == "__main__":
    main()
