# 
# Generic charge calculator driven by pricing parameters stored in a JSON database
#
import json
from datetime import date

class CalcCharge:
    def __init__(self, json_files=None, month=None):
        self.json_files = None
        self.month = None
        self.db = {}
        if json_files is not None:
            self.db = self.load_charge_db(json_files, month)

    def load_charge_db(self, json_files, month=None):
        # return cached db if no key change
        if self.json_files == json_files and self.month == month:
            return self.db

        self.json_files = json_files
        self.month = month

        if month is None:
            month = date.today()
        key = f'{month.year}-{month.month:02}'

        self.db = {}
        for json_file in json_files:
            print('INFO: Opening charge db:', json_file, 'as of:', key)
            with open(json_file) as f:
                ts = json.load(f)
                if 'default' in ts:
                    self.db.update(ts['default'])
                    if key in ts:
                        self.db.update(ts[key])  # selectively overwrite default
                else:
                    self.db.update(ts[key])  # will throw if neither default nor key exists

        return self.db

    def calc_charge(self, contract, usage):
        # TODO: usage may also be a list of hourly usage
        if isinstance(usage, list):
            usage = sum(list)

        # fixed base rate per contract
        if isinstance(self.db['basic'], dict):
            fee = self.db['basic'][contract]
        else:
            fee = self.db['basic']*int(contract)/10

        # variable tiers by usage
        last_tier = 0
        p = usage
        for tier, price in self.db.get('tiers'):
            if tier is None:
                fee += price*p
                break
            else:
                fee += price*(tier-last_tier)
                p -= tier-last_tier
                last_tier = tier

        # fuel adjustment by usage
        fee += self.db.get('nencho', 0.0)*usage

        # renewable adjustment by usage (rounded down)
        fee += int(self.db.get('saiene', 0.0)*usage)

        #print('DEBUG:', self.db)

        return int(fee)

if __name__ == '__main__':
    # Examples
    for plan in ['tepco_b', 'tepco_standard_s', 'tokyo_gas_basic', 'tokyo_gas_1', 'tokyo_gas_1s', 'tokyo_gas_2']:
        cc = CalcCharge(['utils/nencho_saiene.json', 'utils/'+plan+'.json'], date(2026,1,1))
        print(1269, plan, cc.calc_charge('60', 1269))
        cc = CalcCharge(['utils/nencho_saiene.json', 'utils/'+plan+'.json'], date(2026,2,1))
        print(906, plan, cc.calc_charge('60', 906))
        cc = CalcCharge(['utils/nencho_saiene.json', 'utils/'+plan+'.json'], date(2026,3,1))
        print(633, plan, cc.calc_charge('60', 633))
