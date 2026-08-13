"""
TEPCO 検針日カレンダー データ抽出スクリプト

Fetches the 検針日 calendar from the TEPCO website and provides a function
to look up dates by 基準検針日 (district code).

Usage: tepco_kenshinbi.py [collect_base]...

Returns calendar_<year>.json for the given district code, e.g.
{"collect_year": 2026, "collect_base": 2, "collect_date": [2, 5, 3, 4, 6, 7, 4, 6, 4, 3, 5, 4, 3]}%
collect_date index has been normalized to match calendar month (not fiscal)
e.g. collect_date[1]=5 corresponds to Jan 5, 2026
e.g. collect_date[2]=3 corresponds to Feb 5, 2026
"""

import os
import re
import urllib.request
import json
from html.parser import HTMLParser


URL = "https://www.tepco.co.jp/pg/consignment/liberalization/kyoukyusya/change/retail/calendar.html"

# Month order as they appear in the table header (fiscal year: Apr → Mar)


class TableParser(HTMLParser):
    """Minimal HTML parser that extracts <td> / <th> text from the calendar table."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.rows = []
        self._current_row = []
        self._current_cell = None
        self._depth = 0  # track nested tags inside a cell

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        if not self.in_table:
            return
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = []
            self._depth = 1
        elif self._current_cell is not None:
            self._depth += 1

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag == "table":
            self.in_table = False
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = []
        elif tag in ("td", "th"):
            if self._current_cell is not None:
                text = "".join(self._current_cell).strip()
                self._current_row.append(text)
                self._current_cell = None
                self._depth = 0
        elif self._current_cell is not None:
            self._depth -= 1

    def handle_data(self, data):
        if self._current_cell is not None:
            self._current_cell.append(data)


def _fetch_calendar_rows(url: str) -> list[list[str]]:
    """Download the page and return all table rows as lists of cell strings."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = TableParser()
    parser.feed(html)
    return parser.rows


def _build_lookup(rows: list[list[str]]) -> (int, dict[str, list[str]]):
    """
    Parse the raw rows into a dict keyed by 基準検針日.

    Each value is a 13-element list:
      [計量日, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar]
    """
    # Find the data rows: rows whose first cell looks like a 2-digit code (e.g. "01")
    data: dict[str, list[str]] = {}
    year = None
    for row in rows:
        if not row:
            continue
        code = row[0].strip()
        if re.fullmatch(r"\d{2}", code) and len(row) >= 14:
            # row[0] = 基準検針日, row[1] = 計量日, row[2..13] = Apr..Mar
            entry = [None]*13
            entry[0] = int(row[1])
            for i in row[2:]:  # MM/DD
                (mm, dd) = i.split('/', 2)
                entry[int(mm)] = int(dd)
            data[code] = entry
        else:
            match = re.search(r"(\d{4})年度", row[0])
            if match:
                year = int(match.group(1))
    return year, data


# ── Public API ───────────────────────────────────────────────────────────────

_cache: dict[str, list[str]] | None = None
_year: int | None = None

def _get_data() -> dict[str, list[str]]:
    global _year, _cache
    if _cache is None:
        rows = _fetch_calendar_rows(URL)
        _year, _cache = _build_lookup(rows)
    return _cache

def get_year() -> int:
    global _year, _cache
    if _cache is None:
        rows = _fetch_calendar_rows(URL)
        _year, _cache = _build_lookup(rows)
    return _year

def get_kenshinbi(kijun_kenshinbi: str) -> list[str]:
    """
    Return the 検針日 data for the given 基準検針日 (district code).

    Parameters
    ----------
    kijun_kenshinbi : str
        The 基準検針日 code, e.g. "01", "12", "26".
        Zero-padding is applied automatically if a single digit is given.

    Returns
    -------
    list[str]
        A 13-element list where:
          index 0  → 計量日
          index 1  → 4月の検針日
          index 2  → 5月の検針日
          ...
          index 9  → 12月の検針日
          index 10 → 1月の検針日
          index 11 → 2月の検針日
          index 12 → 3月の検針日

        Dates are formatted as "月/日" (e.g. "4/3").

    Raises
    ------
    KeyError
        If the given code is not found in the calendar table.
    """
    code = kijun_kenshinbi.zfill(2)
    data = _get_data()
    if code not in data:
        available = sorted(data.keys())
        raise KeyError(
            f"基準検針日 '{code}' が見つかりません。"
            f"利用可能なコード: {available}"
        )
    return data[code]

def get_available_codes():
    return sorted(_get_data().keys())


# ── CLI demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        print('Usage:', sys.argv[0], '[collect_base]...')

    codes = sys.argv[1:] if len(sys.argv) > 1 else get_available_codes()

    for code in codes:
        try:
            result = get_kenshinbi(code)
            cal = {'collect_year': get_year(), 'collect_base': int(code), 'collect_date': result}
            print(json.dumps(cal))

            # Write calendar file only if there is exactly 1 code provided (o/w assumed to be testing)
            if len(sys.argv) == 2:
                calfile = f'calendar_{get_year()}.json'
                with open(calfile, 'w') as f:
                    print('INFO: writing json to:', calfile)
                    json.dump(cal, f, ensure_ascii=False)
        except KeyError as e:
            print(e)
