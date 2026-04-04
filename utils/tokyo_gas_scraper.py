#
# tokyo_gas_scaper.py
#
# Web scraper to extract pricing parameters for Tokyo Gas plans.
# Output to JSON file for use by home energy monitoring systems.
# Note: fuel cost adjustments, renewable energy adjustments are
# handled separately in a separate web scraper.
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

urls = {
    'tokyo_gas_1s':    'https://home.tokyo-gas.co.jp/gas_power/plan/power/zuttomo1s.html',
    'tokyo_gas_1':     'https://home.tokyo-gas.co.jp/gas_power/plan/power/zuttomo1.html',
    'tokyo_gas_2':     'https://home.tokyo-gas.co.jp/gas_power/plan/power/zuttomo2.html',
    'tokyo_gas_basic': 'https://home.tokyo-gas.co.jp/gas_power/plan/power/menu_basic.html'
}

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
# TARIFF 
# ------------------------

def extract_tariff(html):
    parser = TableParser()
    parser.feed(html)

    basic = {}
    tiers = []

    # --- Basic charges ---
    # '契約電流 10A 1契約 311. 74 円'
    for row in parser.tables[0]:
        if len(row) < 3:
            continue
        base  = re.search(r"(\d+)A", row[0])
        price = normalize_price(''.join(row[-3:]))
        if base and price:
            basic[base.group(1)] = price
        elif price and row[1] == '1kVA':
            basic = price

    # --- Energy tiers ---
    # '第1段階料金（120kWhまで） 1kWh 29. 70 円'
    for row in parser.tables[1]:
        if len(row) < 3:
            continue
        n = re.search(r"第(\d)段階料金", row[0])
        if not n:
            continue
        if re.findall(r"超えた", row[0]):  # final tier, can ignore lower limit
            nums = []
        else:
            nums = list(map(int, re.findall(r"(\d+)kWh", row[0])))
            nums = nums[-1] if nums else None  # just need the upper limit
        price = normalize_price(''.join(row[-3:]))
        if n and price:
            tiers.append((nums, price))

    return basic, tiers


# ------------------------
# NORMALIZATION
# ------------------------

def normalize_all(ts_data, basic, tiers, plan, today):
    out = ts_data
    out[today] = {}

    # --- Header ---
    out['default'] = {}
    out['default']['plan'] = plan
    out['default']['last_updated'] = str(datetime.now().astimezone())

    # --- Basic charges ---
    out[today]['base'] = basic

    # --- Energy tiers ---
    out[today]['tiers'] = tiers

    return out


# ------------------------
# MAIN
# ------------------------

def main():
    if len(sys.argv) < 3 or sys.argv[1] not in urls:
        print('Usage:', sys.argv[0], 'plan [charge_db.json|--nodate] new_charge_db.json', file=sys.stderr)
        print('plan must be one of:', ' '.join(urls.keys()))
        sys.exit(1)

    dbfile = None
    today  = date.today().isoformat()[:7]  # YYYY-MM
    URL = urls[sys.argv[1]]
    if len(sys.argv) > 3:
        if sys.argv[2] == '--nodate':
            today  = 'default'    # use 'default' when you don't want to keep track of rate changes over time
        else:
            dbfile = sys.argv[2]  # existing db file to merge into
        dbfile_new = sys.argv[3]
    else:
        dbfile_new = sys.argv[2]

    tariff_html = fetch(URL)

    basic, tiers = extract_tariff(tariff_html)

    # Optionally merge with existing json db 
    ts_data = {}
    if dbfile is not None:
        try:
            print('INFO: reading json from:', dbfile)
            with open(dbfile) as f:
                ts_data = json.load(f)
        except FileNotFoundError:
            print('ERROR: file not found:', dbfile)
            exit(-1)

    ts_data = normalize_all(ts_data, basic, tiers, sys.argv[1], today)

    print(json.dumps(ts_data, indent=2, ensure_ascii=False, sort_keys=True))

    with open(dbfile_new, 'w') as f:
        print('INFO: writing json to:', dbfile_new)
        json.dump(ts_data, f, indent=2, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    main()
