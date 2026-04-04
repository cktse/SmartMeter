#
# tepco_scaper.py
#
# Web scraper to extract pricing parameters for TEPCO.
# Output to JSON file for use by home energy monitoring systems.
# Note: fuel cost adjustments, renewable energy adjustments are
# handled separately in a separate web scraper.
#

import urllib.request
from html.parser import HTMLParser
import re, sys, json
from datetime import date, datetime

urls = {
    'tepco_standard_s': "https://www.tepco.co.jp/ep/private/plan/standard/kanto/index-j.html",
    'tepco_standard_l': "https://www.tepco.co.jp/ep/private/plan/standard/kanto/index-j.html",
    'tepco_standard_x': "https://www.tepco.co.jp/ep/private/plan/standard/kanto/index-j.html",
    'tepco_b': "https://www.tepco.co.jp/ep/private/plan/old01.html",
    'tepco_c': "https://www.tepco.co.jp/ep/private/plan/old01.html"
}


# --- Tepco HTML parser ---
class TepcoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.records = []
        self.plan = None
        self.last_text = None

        # state flags for parsing standard plans (no tables)
        self.mode = None  # "basic" or "tiers"
        self.range = None

        # table parser
        self.in_td = False
        self.current_row = []
        self.current_table = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            attrs_dict = dict(attrs)
            src = attrs_dict.get("src", "")

            # --- Plan detection via IMG filename ---
            if "standard_s" in src.lower():
                self.plan = "tepco_standard_s"
            elif "standard_l" in src.lower():
                self.plan = "tepco_standard_l"
            elif "standard_x" in src.lower():
                self.plan = "tepco_standard_x"
        elif tag == "td" or tag == 'th':
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
        text = data.strip()
        if not text:
            return

        # --- Cache table rows
        if self.in_td:
            self.current_row.append(text)
            return

        # --- Detect sections ---
        if "基本料金" in text:
            self.mode = "basic"
            return

        if "電力量料金" in text:
            self.mode = "tiers"
            return

        # --- Base pricing ---
        if self.mode == "basic" and "円"==text[-1]:
            self.records.append({
                "plan": self.plan,
                "type": "basic",
                "price": extract_number(text)
            })
            return

        # --- Energy pricing ---
        if self.mode == "tiers":
            m = re.search(r'(\d+)kWh〜(\d+)kWh', text)
            if m:
                self.range = int(m.group(2))
                return
            m = re.search(r'^〜(\d+)kWh', text)
            if m:
                self.range = int(m.group(1))
                return
            m = re.search(r'(\d+)kWh〜$', text)
            if m:
                self.range = -1
                return

            if "円"==text[-1] and self.range:
                self.records.append({
                    "plan": self.plan,
                    "type": "tiers",
                    "range": self.range if self.range > 0 else None,
                    "price": extract_number(text)
                })
                self.range = None
                return

# --- Extract tariff parameters from HTML ---
def extract_tariff(plan, html):
    parser = TepcoParser()
    parser.feed(html)

    tables = parser.tables

    basic = {}
    tiers = []

    # for standard plans, there are no table structure so lean on streaming tags during parsing
    if 'standard' in plan:
        n = 0
        for row in parser.records:
            if row['plan'] == plan:
                if row['type'] == 'basic':
                    basic = row['price']
                elif row['type'] == 'tiers':
                    tiers.append((row['range'], row['price']))
        return basic, tiers

    # for legacy B/C plans, extract from cached tables

    # --- Basic charges ---
    basic = {}
    table = parser.tables[0 if '_b' in plan else 3]
    for row in table:
        if len(row) < 3:
            continue

        price = extract_number(row[-1])
        if price is None:
            continue

        if row[1] == '1kVA':  # 1kVA multiplier
            basic = price
            break

        label = row[0]+" "+row[1]  # cater for th rowspan
        m = re.search(r"(\d+)A", label)
        if m:
            basic[m.group(1)] = price  # Amp-Price table format

    # --- Energy tiers ---
    tiers = []
    table = parser.tables[1 if '_b' in plan else 4]
    for row in table:
        if len(row) < 3:
            continue

        label = row[0]+" "+row[1]  # cater for th rowspan
        price = extract_number(row[-1])
        if price is None:
            continue

        m = re.search(r"第(\d)段階料金", label)
        if not m:
            continue

        nums = list(map(int, re.findall(r"(\d+)kWh", label)))
        nums = nums[-1] if nums else None  # just need the upper limit
        tiers.append((nums, price))

    return basic, tiers


# ------------------------
# HELPERS
# ------------------------

def fetch(url):
    with urllib.request.urlopen(url) as r:
        return r.read().decode("utf-8")


def extract_number(text):
    text = text.replace(",", "")
    m = re.search(r"(-?\d+)円(\d+)銭", text)
    if m:
        return float(m.group(1))+float(m.group(2))/100

    m = re.search(r"(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None


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

    # --- Base charges ---
    out[today]['basic'] = basic

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

    tariff_html = fetch(urls[sys.argv[1]])
    
    basic, tiers = extract_tariff(sys.argv[1], tariff_html)

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
