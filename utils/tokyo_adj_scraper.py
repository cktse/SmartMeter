#
# tokyo_adj_scraper.py
#
# Web scraper to extract 1) fuel cost adjustments and 2) renewable energy adjustments for the Tokyo region.
# Output to JSON file for use by home energy monitoring systems.
#
# Notes:
# 1) Scrap from TEPCO web site -- these adjustment data are also applicable to other energy providers 
#    (Tokyo Gas etc.) for the Tokyo (Kanto) region
# 2) Output JSON is indexed by date (YYYY-MM) which is the billing month cycle. The prior version of
#    JSON can be supplied from the command line so that new month(s) are incrementally added to the output
#    JSON as and when TEPCO web pages are updated with new data.
#

import urllib.request
import re
import sys
import json
from html.parser import HTMLParser
from datetime import date, datetime


# ------------------------
# CONFIG 
# ------------------------

FUEL_URL = "https://www.tepco.co.jp/ep/private/fuelcost2/newlist/index-j.html"
RENEWABLE_URL = "https://www.tepco.co.jp/ep/renewable_energy/institution/impost.html"


# ------------------------
# GENERIC TABLE PARSER
# ------------------------

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.current_row = []
        self.current_table = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        if tag == "td" or tag == 'th':
            self.in_td = True
        elif tag == "tr":
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "td" or tag == 'th':
            self.in_td = False
        elif tag == "tr":
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag == "table":
            if self.current_table:
                self.tables.append(self.current_table)
                self.current_table = []

    def handle_data(self, data):
        if self.in_td:
            text = data.strip()
            if text:
                self.current_row.append(text)


# ------------------------
# HELPERS
# ------------------------

def fetch(url):
    with urllib.request.urlopen(url) as r:
        return r.read().decode("utf-8")


def normalize_price(text):
    # 円銭 format
    m = re.search(r"(-?\d{1,3}(?:,\d{3})*)円(\d+)銭", text)
    if m:
        return float(m.group(1).replace(",","")) + float(m.group(2)) / 100

    # ▲ or decimal format
    m2 = re.search(r"(▲?\d{1,3}(?:,\d{3})*\.\d+)", text)
    if m2:
        return float(m2.group(1).replace("▲", "-").replace(",",""))

    return None


# ------------------------
# FUEL COST ADJUSTMENT
# ------------------------

def extract_fuel(html):
    parser = TableParser()
    parser.feed(html)

    results = []
    current_year = None

    for table in parser.tables:
        joined = " ".join(cell for row in table for cell in row)

        if "燃料費調整" not in joined or "電気需給約款［低圧］" not in joined:
            continue

        for row in table:
            text = " ".join(row)

            y = re.search(r"(\d{4})年", text)
            if y:
                current_year = int(y.group(1))

            m = re.search(r"(\d{1,2})月分", text)
            if m:
                month = int(m.group(1))

                # prioritize rightmost column
                for cell in reversed(row):
                    price = normalize_price(cell)
                    if price is not None:
                        results.append((current_year, month, price))
                        break

    # sort newest first
    results.sort(key=lambda x: (x[0], x[1]), reverse=True)

    return results


# ------------------------
# RENEWABLE ENERGY
# ------------------------

def extract_renewable(html):
    parser = TableParser()
    parser.feed(html)

    results = []

    for table in parser.tables:
        joined = " ".join(cell for row in table for cell in row)

        if "低圧供給（従量制）" not in joined:
            continue

        for row in table:
            if len(row) < 2:
                continue

            text = " ".join(row)

            # 2026年5月分から2027年4月分まで 4.18円/kWh
            # 【参考】2026年4月分 3.98円/kWh
            y1 = re.search(r"(\d{4})年(\d{1,2})月", text)
            y2 = re.search(r"(\d{4})年(\d{1,2})月分まで", text)
            p  = re.search(r"(\d+\.\d+)\s*円", text)

            if y1 and y2 and p:
                results.append((int(y1.group(1)), int(y1.group(2)), int(y2.group(1)), int(y2.group(2)), float(p.group(1))))
            elif y1 and p:
                results.append((int(y1.group(1)), int(y1.group(2)), int(y1.group(1)), int(y1.group(2)), float(p.group(1))))

    # dedupe + sort
    results = list(set(results))
    results.sort(key=lambda x: x[0], reverse=True)

    return results


# ------------------------
# NORMALIZATION
# ------------------------

def normalize_all(ts_data, fuel, renewable):
    out = ts_data

    # --- Header ---
    if 'default' not in out:
        out['default'] = {}
    out['default']['last_updated'] = str(datetime.now().astimezone())

    # --- Fuel adjustment (monthly) ---
    for year, month, price in fuel:
        key = f'{year}-{month:02}'
        if key not in out:
            out[key] = {}
        out[key]['nencho'] = price

    # --- Renewable surcharge (expand to monthly) ---
    for y1, m1, y2, m2, price in renewable:
        y = y1
        m = m1
        while y <= y2 and not (y == y2 and m > m2):
            key = f'{y}-{m:02}'
            if key not in out:
                out[key] = {}
            out[key]['saiene'] = price
            if m < 12:
                m += 1
            else:
                y += 1
                m = 1

    return out


# ------------------------
# MAIN
# ------------------------

def main():
    if len(sys.argv) < 2:
        print('Usage:', sys.argv[0], '[charge_db.json] new_charge_db.json', file=sys.stderr)
        sys.exit(1)
    if len(sys.argv) > 2:
        dbfile     = sys.argv[1]
        dbfile_new = sys.argv[2]
    else:
        dbfile     = None
        dbfile_new = sys.argv[1]

    fuel = extract_fuel(fetch(FUEL_URL))
    renewable = extract_renewable(fetch(RENEWABLE_URL))

    # Open existing json db, if any
    ts_data = {}
    if dbfile is not None:
        try:
            print('INFO: reading json from:', dbfile)
            with open(dbfile) as f:
                ts_data = json.load(f)
        except FileNotFoundError:
            print('Warning: file not found:', dbfile)

    ts_data = normalize_all(ts_data, fuel, renewable)

    print(json.dumps(ts_data, indent=2, ensure_ascii=False, sort_keys=True))

    with open(dbfile_new, 'w') as f:
        print('INFO: writing json to:', dbfile_new)
        json.dump(ts_data, f, indent=2, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    main()
