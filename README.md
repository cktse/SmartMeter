# SmartMeter

Part of my Japan "Smart Home" Project: monitor energy usage in real-time and publish into Home Assistant for trending and analysis.
<img width="1195" height="896" alt="SmartMeter+HA" src="https://github.com/user-attachments/assets/cf315b49-f745-462d-ad59-9f4e225b9ea9" />
<img width="2812" height="1334" alt="SmartMeter+HA Dashboard" src="https://github.com/user-attachments/assets/c2f01d9c-fe23-45bb-ab14-00093bfc76d4" />

As of 2026, most if not all meters in Japan have been upgraded to [Smart Meter](https://www.tepco.co.jp/en/pg/development/domestic/smartmeter-e.html) which supports the so called "Route B" service, made available electricity meter data in real-time over a 920Mhz radio [Wi-SUN](https://wi-sun.org/about/). Any consumer can apply for the Route B login credential and, with the right hardware and software, connect to the smart meter at home to monitor energy usage. This forms part of the [ECHONET Lite](https://echonet.jp/features_en/) standard which details the communication protocol between hundreds of different types of home appliances to enable home energy management systems.

## Why another fork?

While a number of similar projects had existed for some time, I ended up chosing Miyaichi-san's design as the baseline to build on. Reasons being:

- Micropython being a scripting language allows for rapid iteration, perfect for someone learning about IoT dev
- [M5StickC-PLUS2](https://docs.m5stack.com/zh_CN/core/M5StickC%20PLUS2) is a slick ESP32 device with its own color LCD screen to show real-time data at a glance
- Simple and lightweight code base with minimal dependencies as a starting point, for example this very nice [project](https://github.com/yonmas/SMM3-SmartMeterMonitor_v3?tab=readme-ov-file) supports relaying data to another child device for visualization which I won't need as I plan to integrate with Home Assistant. I also prefer not to introduce internet dependency by using Google Sheet to store configuration details.

## New Features Added

- Support the newer device M5StickC-PLUS2 and Wi-SUN HAT rev0.2 (see Hardware below)
- Migrate to the latest UIFlow 2.0 firmware (V2.5) based on Micropython v1.27.0 -- major API changes with the unified M5 library replacing the legacy M5Stack library
- Run as an energy sensor to publish real-time usage data into Home Assistant over MQTT
- Improve accuracy of Tepco charge calculator -- support the [meter reading day (検針日)](https://www.tepco.co.jp/pg/consignment/liberalization/kyoukyusya/change/retail/calendar.html) calendar including utility scripts to scrap data off the TEPCO web site

## Route B Service

- Apply online for the [Route B Service](https://www.tepco.co.jp/pg/consignment/liberalization/smartmeter-broute.html) -- this link is for TEPCO but there should be similar links for other providers
- You will receive an email from route_b_information@tepco.co.jp containing a 12-character password -- note that the embedded spaces are just there for readability and are not part of the password!
- Interestingly, you will only receive the 32-character user ID by post (same address as your billing address) -- why is this not the other way round is beyond me. Similarly note that the embedded spaces are just there for readability

## Hardware

- [M5StickC-PLUS2](https://www.switch-science.com/products/9350) - ESP32 controller with a nice color display and expandable I/O
- Note that the new board [M5StickS3](https://www.switch-science.com/products/10921) released in March 2026 is sadly pin-incompatible with Wi-SUN HAT (HAT2 is now 16-pin) It also lacks RTC, so may not be ideal for real-time energy tracking use cases
- [BP35A1](https://www.rohm.com/products/wireless-communication/specified-low-power-radio-modules/bp35a1-product#productDetail) -- Wi-SUN Compatible Wireless Module, EOL as of 2026 so only available while stock lasts
- [BP35C1-J11-T01]() -- alternative to BP35A1, evaluation board for the newer, surface mount [BP35C0-J11](https://www.rohm.com/products/wireless-communication/specified-low-power-radio-modules/bp35c0-j11-product) module
- [Wi-SUN HAT rev0.2](https://booth.pm/ja/items/1650727) -- M5Stick HAT kit for the Wi-SUN module, make sure to buy the matching version for BP35A1 vs. BP35C1-J11-T01.
- If you end up finding an old rev0.1 stock, you will need to modify the python code to use GPIO pin 36 instead of 26 for the UART Rx line.

## Software

### Firmware

Flash the M5StickC-PLUS2 with UIFlow 2.0 firmware (V2.5.0 or later) using [M5Burner5](https://docs.m5stack.com/en/uiflow/m5burner/intro) Make sure the Boot Option `Run main.py directly` is selected instead of the default `Show startup menu and network setup`, which would break `mpremote`. Also make sure Timezone is `GMT+9`.

### Local Timezone Support
Note that firmware comes with local timezone support (GMT+9 for Japan) which must be configured at the time of burning. There was a firmware bug (found on V2.4.3) which caused the timezone to flip-flop between GMT+9 and GMT-9 on every reboot which was resolved by upgrading to V2.5.0. This repository now assumes that utime.localtime() is reliable and hence removed the need for manual +9 hours offset in the code. If this becomes problematic for your specific device/firmware, consider hacking the +9 hours offset in `ntptime.py` when setting RTC.

### Clone this repository

```bash
git clone https://github.com/cktse/SmartMeter.git
cd SmartMeter
```

### Dependencies

Everything needed at runtime is either bundled with the UIFlow 2.0 firmware (`M5`, `umqtt.simple`, `network`, `machine`) or included in this repository (`BP35A1.py`, `mqtt.py`, `charge.py`, `chargedb.py`, `ntptime.py`, `logging.py`). No `pip install` etc. to keep dependencies to a minimal. No external cloud services so all of your data stay local by default (unless you opt into Ambient -- see below).

- `ntptime.py` here is the standard Micropython module with the NTP host defaulted to `jp.pool.ntp.org` -- TODO: revert to the firmware version to reduce clutter
- `logging.py` is a simple fork of the micropython-lib logging module -- TODO: enable datetime logging; explore [micropython-ulogging](https://github.com/iabdalkader/micropython-ulogging)
- [Home Assistant](https://www.home-assistant.io) integration (optional) is built-in via MQTT broker
- [Ambient](https://ambidata.io/) is still available as an optional cloud sink -- see [Ambient (optional)](#ambient-optional) below

### Copy configuration file

```bash
cp SmartMeter.example.json SmartMeter.json
```

### Configuration

#### SmartMeter.json

Holds the Route B credential used to reach the smart meter, the contracted amperage (契約アンペア数) and meter reading day (検針日) used to work out monthly usage, and -- if you are integrating with Home Assistant -- the MQTT broker connection details.

| Name              | Description                                        | Example                                              |
| ----------------- | -------------------------------------------------- | ---------------------------------------------------- |
| wifi_ssid         | Wi-Fi SSID                                         | "XXXXXXXXXXXX" |
| wifi_password     | Wi-Fi Password                                     | "XXXXXXXXXXXX" |
| id                | Route B ID (32 characters)                         | "000000XXXXXX00000000000000XXXXXX"                   |
| password          | Route B password (12 characters)                   | "XXXXXXXXXXXX"                                       |
| contract_amperage | Contracted amperage (契約アンペア数)               | "60"                                                 |
| charge_func       | Charge calculation function, see charge.py         | "tepco"                                              |
| collect_date      | Meter reading day (検針日), fallback if no calendar | "4"                                                 |
| mqtt              | MQTT broker connection details                     | see below                                            |
| ambient           | Ambient channel details (optional)                 | {"channel_id": "XXXXX","write_key": "XXXXXXXXXXXXXXXX"} |

The `mqtt` block:

| Name             | Description                                           | Example              |
| ---------------- | ----------------------------------------------------- | -------------------- |
| server           | MQTT broker hostname or IP                            | "homeassistant.local"|
| port             | MQTT broker port                                      | "1883"               |
| user             | MQTT username                                         | "XXXXXX"             |
| password         | MQTT password                                         | "XXXXXXXXXXXXXXXXXXXX" |
| discovery_prefix | Home Assistant discovery prefix, defaults to "homeassistant" | "homeassistant" |

Both `mqtt` and `ambient` are optional -- drop the whole block and that publisher is simply not started, leaving the device as a standalone LCD display. If a block is present, all of its keys must be present for the device to start up.

Note that `SmartMeter.json` holds your Route B credential and MQTT password in clear text, so it is gitignored here -- only `SmartMeter.example.json` is tracked.

### Home Assistant over MQTT

This is the main reason for the fork. On startup, after the Route B session with the meter is established, the device announces itself to Home Assistant using [MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery) and then keeps publishing state -- zero-configuration on the Home Assistant side, the sensors just appear.

The meter identifies itself over ECHONET Lite with its manufacturer code (メーカーコード, EPC `8A`) and production number (製造番号, EPC `8D`), which are used to build a stable device ID of the form `smartmeter_<manufacturer_code>_<production_number>`. Because the ID is derived from the meter and not from the M5Stick, you can replace or re-flash the controller without orphaning the history in Home Assistant.

| Entity                             | Unit | device_class | state_class      | Source                                          |
| ---------------------------------- | ---- | ------------ | ---------------- | ----------------------------------------------- |
| Instantaneous Power                | W    | power        | measurement      | Instantaneous power (瞬時電力計測値, E7)        |
| Instantaneous Current (R phase)    | A    | current      | measurement      | Instantaneous current (瞬時電流計測値, E8)      |
| Instantaneous Current (T phase)    | A    | current      | measurement      | Instantaneous current (瞬時電流計測値, E8)      |
| Cumulative Energy                  | kWh  | energy       | total_increasing | Cumulative energy, normal direction (積算電力量計測値, EA) |
| Cumulative Energy (Reverse)        | kWh  | energy       | total_increasing | Cumulative energy, reverse direction (逆方向, EB) |
| Monthly Energy                     | kWh  | energy       | total            | EA minus the reading at the last meter reading day |
| Monthly Charge                     | JPY  | monetary     | total            | calculated, see charge calculation below        |

- R phase and T phase currents are published separately rather than summed. Single-phase three-wire (単相3線式) service splits the load across two phases and adding them up is not physically meaningful -- let Home Assistant template them if you want a single number. The on-device LCD still shows the sum for a quick glance
- `Cumulative Energy` is the meter's own lifetime total, which is what you want to feed into the Home Assistant Energy Dashboard as a `total_increasing` source. `Monthly Energy` is derived on device from the meter reading day (検針日) and resets every billing period, so it is `total` rather than `total_increasing`
- `Cumulative Energy (Reverse)` (EB, e.g. export from solar) is declared but not populated yet -- see [Open questions / features planned](#open-questions--features-planned)

Topics used:

```
homeassistant/sensor/smartmeter_<mfr>_<serial>/<entity>/config   # discovery, retained
echonet/smartmeter_<mfr>_<serial>/<entity>/state                 # state, retained
```

State is retained so that a restarting Home Assistant picks up the last known values immediately instead of showing `unknown` until the next publish. Discovery configs are cleared (empty retained payload) and re-published on every connect, so changes to the entity definitions in `mqtt.py` take effect on the next boot rather than leaving stale entities behind.

Publishing cadence follows the polling loop: instantaneous power and current every 10s, monthly energy / charge / cumulative energy every 60s. The Route B radio link is the bottleneck here, not MQTT -- there is little point polling the meter faster. Publishing happens inside the same `try` as the meter read, so a failed read skips the publish instead of re-sending the previous value.

If the broker connection drops, the publish helper flags the connection as down and retries on the next cycle, re-running discovery once it is back. Wi-Fi is checked (and bounced if necessary) on the same path. The intent is that a broker or Wi-Fi outage degrades the device to a local display rather than taking it down -- meter polling and the LCD keep working regardless.

`mqtt.py` can also be run standalone on the device for testing, which publishes discovery plus a set of dummy values so you can confirm the entities show up in Home Assistant before the real meter session is up.

#### Charge calculation

Given the contracted amperage (契約アンペア数) and the meter reading day (検針日), the electricity charge can be estimated reasonably well. The rate tables live in JSON and are processed by the generic calculation engine in `chargedb.py`; `charge.py` is just a thin wrapper per tariff plan, and you pick one by name via `charge_func` in `SmartMeter.json` (e.g. `"charge_func": "tepco"`).

Presets provided in `charge.py`: `tepco` (TEPCO 従量電灯B), `tokyo_gas_1` (Tokyo Gas ずっとも電気1), `tokyo_gas_1s`, `tokyo_gas_2`. Each one loads a pair of JSON files -- the tariff plan (e.g. tepco_b.json) plus adjustments (nencho_saiene.json) Total charge is the sum of:

- Base rate (基本料金) -- flat rate looked up by contracted amperage (or per-10A prorated, for plans priced that way)
- Energy rate (電力量料金) -- tiered by usage, e.g. TEPCO 従量電灯B is 120kWh / 300kWh / above
- Fuel cost adjustment (燃料費調整額, `nencho`) -- per kWh, changes monthly and is frequently negative
- Renewable energy levy (再生可能エネルギー発電促進賦課金, `saiene`) -- per kWh, changes annually in May

Because the fuel and renewable adjustments are dated, the JSON db is keyed by `YYYY-MM` with an optional `default` block; the entry for the month being billed is merged over the default. This is what makes the estimate track reality across a rate change instead of drifting. Note that there may be special discount given on top which are not modeled -- the goal is a number that trends correctly, not an exact invoice.

To add your own plan, drop a JSON file next to the others following the same `basic` / `tiers` shape (potentially a new web scraper in `utils/`) and add a three-line wrapper to `charge.py`.

#### Meter reading day (検針日) calendar

The TEPCO meter reading day is not a fixed day of the month -- it varies by month and by district code (基準検針日, 1 to 5, printed on your bill). Getting this wrong shifts the whole monthly total, so `calendar_<year>.json` carries the actual per-month schedule:

```json
{"collect_year": 2026, "collect_base": 2, "collect_date": [2, 5, 3, 4, 6, 7, 4, 6, 4, 3, 5, 4, 3]}
```

`collect_date` is indexed by calendar month -- index 1 = January through index 12 = December -- so `collect_date[month]` is a direct lookup (normalized from the fiscal year layout on the TEPCO web site). Index 0 holds the metering day (計量日) as scraped and is overwritten at startup with December's value, which is what makes the "previous month" lookup wrap correctly in January.

If no calendar file for the current year is found on the device, the scalar `collect_date` from `SmartMeter.json` is expanded to all 13 entries, which is the old fixed-day behaviour.

#### Refreshing the tariff and calendar data

Rates and the calendar both go stale -- the fuel cost adjustment monthly, the renewable levy every May, the calendar every fiscal year (年度). The scrapers in `utils/` pull them straight off the utility web sites; these are meant to run off device (e.g. on the Home Assistance Green)

```bash
make refresh          # runs utils/refresh.sh: scrapes all three, keeps the previous copy as old_*.json
make                  # copies the refreshed json from utils/ into the staging root
```

`refresh.sh` is deliberately conservative: each JSON is only rotated out when the scraper that produced its replacement exited cleanly, so a web site redesign leaves you with stale-but-valid data rather than an empty file. It also prints a `diff -c` of what changed, which is worth eyeballing before pushing anything to the device. Edit the top of the script to match your own plan and district code (`COLLECT_BASE`).

The individual scrapers can also be run by hand from `utils/`:

```bash
python tepco_scraper.py tepco_b --nodate tepco_b.json   # rate table (--nodate: store as 'default', no rate history)
python tokyo_adj_scraper.py nencho_saiene.json new.json # fuel / renewable adjustments, merged into existing db
python tepco_kenshinbi.py 2                             # meter reading day calendar for district code 2
```

#### Ambient (optional)

The original project's [Ambient](https://ambidata.io/) integration is still in place for anyone who wants a hosted chart without running Home Assistant. Set the `ambient` block in `SmartMeter.json` and download the module:

```bash
curl -o ambient.py https://raw.githubusercontent.com/AmbientDataInc/ambient-python-lib/master/ambient.py
```

Data is sent every 30s, i.e. 2,880 times a day, under Ambient's limit of 3,000:

| Name   | Unit | Description                                                    |
| ------ | ---- | -------------------------------------------------------------- |
| data 1 | A    | Instantaneous current (瞬時電流計測値, E8) -- R + T summed      |
| data 2 | W    | Instantaneous power (瞬時電力計測値, E7)                        |
| data 3 | kWh  | Energy used this billing period, since the last 検針日 (EA)     |
| data 4 | JPY  | Estimated charge for this billing period                        |

## Install

Copy the required files onto the M5StickC-PLUS2. Under UIFlow 2.0, scripts placed in `/flash/apps/` show up in the boot menu. The Makefile drives everything over [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html):

```bash
make refresh          # run web scrapers to refresh json files in utils/
make                  # copy json files from utils/ into staging
make connect          # serial REPL (^C to break out of boot, ^] to exit mpremote)
make push             # copy config + modules + app from staging to the device
make run              # run apps/SMM.py from staging, without installing
```

`make connect` uses a hardcoded serial device path -- adjust it to whatever your board enumerates as.

What ends up where:

/flash/apps/

- SMM.py

/flash/

- BP35A1.py
- mqtt.py
- charge.py
- chargedb.py
- ntptime.py
- logging.py
- SmartMeter.json
- tepco_b.json (or whichever tariff your `charge_func` loads)
- nencho_saiene.json
- calendar_2026.json (meter reading day calendar for the current year)
- ambient.py (only if using Ambient)

## Debug

Logs are emitted at DEBUG level. Connect to the M5StickC serial console to watch what the device is doing:

```bash
make connect
make run
```

Useful things to look for on the console:

- `BP35A1 config:` / `Connected. BP35A1 info:` -- the Route B session came up (scan can take a couple of minutes on first join)
- `MQTT config:` -- broker details as actually parsed from `SmartMeter.json`
- `Discovery:` lines -- one per entity announced to Home Assistant
- `collect_date:` -- the meter reading day list in use, i.e. whether the calendar file was found

On the broker side, `mosquitto_sub -h <broker> -u <user> -P <pass> -t 'echonet/#' -v` is the quickest way to confirm state is flowing independently of Home Assistant.

## Open questions / features planned

- **JSON config refresh/date rollover** -- need an automated way for the device to pick up refreshed JSON files periodically
- **Reverse direction (逆方向, EB) cumulative energy** -- the `Cumulative Energy (Reverse)` entity is declared in `mqtt.py` but never published. `BP35A1.monthly_power()` only reads EA; EB needs to be read and, more interestingly, factored into the monthly total for a household with solar. No solar here to test against
- **R + T phase handling** -- the LCD shows `amperage_r + amperage_t`, which is not what single-phase three-wire (単相3線式) actually means. The MQTT side already publishes the two phases separately; the display (and Ambient data 1) still needs a better answer than a sum
- **Surviving a Wi-Fi outage** -- `checkWiFi()` bounces the interface and gives up gracefully, and the periodic watchdog timer is currently commented out because a reboot mid-session costs a slow Route B re-join. Meter polling and the LCD should keep working indefinitely without a network; this has not been properly soak tested
- **Manufacturer code lookup** -- `MANUFACTURERS` in `mqtt.py` only maps a handful of codes (the full list is defined by the ECHONET consortium and is too big to carry on device). Unknown codes fall back to the raw hex, which works but reads badly in Home Assistant. Send a PR if your meter's maker is missing
- **Logging in `mqtt.py`** -- still uses bare `print()` rather than the logger, so MQTT chatter cannot be filtered by log level
- **Hourly usage** -- `CalcCharge.calc_charge()` takes a single total. Time-of-use plans (and any real off-peak / night rate modelling) need a list of hourly usage, which the meter can provide as cumulative energy history (積算電力量計測値履歴) but the code does not read yet
- **BP35C1-J11 support** -- the driver is written against BP35A1's SK command set. The newer module is close but not identical, and is untested here

## Credit

- [miyaichi/SmartMeter](https://github.com/miyaichi/SmartMeter) -- the original project this is forked from

- [M5StickC で家庭用スマートメーターをハックする！](https://kitto-yakudatsu.com/archives/7206)

- [B ルートやってみた - スカイリー・ネットワークス](http://www.skyley.com/products/b-route.html)

- [特定省電力無線モジュール BP35A1 スタートガイド](https://micro.rohm.com/jp/download_support/wi-sun/data/other/bp35a1-startguide_v150.pdf)

- [BP35A1 コマンドリファレンスマニュアル（SE 版）](https://rabbit-note.com/wp-content/uploads/2016/12/50f67559796399098e50cba8fdbe6d0a.pdf)

- [ECHONET 規格書 Version 3.21 （日本語版）/ APPENDIX ECHONET 機器オブジェクト詳細規定](https://echonet.jp/spec_g/#standard-02)

- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
