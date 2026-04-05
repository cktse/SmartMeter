#
# Preset charge calculators for some common energy providers & plans.
# All calculators have been re-factored to use the generic CalcCharge based on JSON config.
# Only the one configured in SmartMeter.json is actually used, so feel free to 
# make changes / trim down this file as needed.
#

from chargedb import CalcCharge

_db = CalcCharge()

def tepco(contract, usage, month=None):
    global _db
    _db.load_charge_db(['utils/nencho_saiene.json', 'utils/tepco_b.json'], month)
    return _db.calc_charge(contract, usage)
            
def tokyo_gas_1(contract, usage, month=None):
    global _db
    _db.load_charge_db(['utils/nencho_saiene.json', 'utils/tokyo_gas_1.json'], month)
    return _db.calc_charge(contract, usage)

def tokyo_gas_1s(contract, usage, month=None):
    global _db
    _db.load_charge_db(['utils/nencho_saiene.json', 'utils/tokyo_gas_1s.json'], month)
    return _db.calc_charge(contract, usage)

def tokyo_gas_2(contract, usage, month=None):
    global _db
    _db.load_charge_db(['utils/nencho_saiene.json', 'utils/tokyo_gas_2.json'], month)
    return _db.calc_charge(contract, usage)

if __name__ == '__main__':
    # Examples
    from datetime import date
    print(339, tokyo_gas_1('60', 339))
    print(339, tepco('60', 339))
    print(633, tokyo_gas_1('60', 633, date(2026,3,1)))
    rint(633, tepco('60', 633, date(2026,3,1)))
