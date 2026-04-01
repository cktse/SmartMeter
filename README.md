# SmartMeter

Part of my Japan "Smart Home" Project: monitor energy usage in real-time and publish into Home Assistant for trending and analysis. 

As of 2026, most if not all meters in Japan have been upgraded to [Smart Meter](https://www.tepco.co.jp/en/pg/development/domestic/smartmeter-e.html) which supports the so called "Route B" service, made available electricity meter data in real-time over a 920Mhz radio [Wi-SUN](https://wi-sun.org/about/). Any consumer can apply for the Route B login credential and, with the right hardware and software, connect to the smart meter at home to monitor energy usage. This forms part of the [ECHONET Lite](https://echonet.jp/features_en/) standard which details the communication protocol between hundreds of different types of home appliances to enable home energy management systems.

## Why another fork?

While a number of similar projects had existed for some time, I ended up chosing Miyaichi-san's design as the baseline to build on. Reasons being:

- Micropython being a scripting language allows for rapid iteration, perfect for someone learning about IoT dev
- [M5StickC-PLUS2](https://docs.m5stack.com/zh_CN/core/M5StickC%20PLUS2) is a slick ESP32 device with its own color LCD screen to show real-time data at a glance
- Simple and lightweight code base with minimal dependencies as a starting point, for example this very nice [project](https://github.com/yonmas/SMM3-SmartMeterMonitor_v3?tab=readme-ov-file) supports relaying data to another child device for visualization which I won't need as I plan to integrate with Home Assistant. I also prefer not to introduce internet dependency by using Google Sheet to store configuration details.

## Features planned

- Support the newer device M5StickC-PLUS2 and Wi-SUN HAT rev0.2 (see Hardware below)
- Migrate to the latest UIFlow 2.0 firmware (V2.4.3) based on Micropython v1.25.0 -- major API changes with the unified M5 library replacing the legacy M5Stack library
- Run as an energy sensor to publish real-time usage data into Home Assistant over MQTT
- Improve accuracy of Tepco charge calculator -- support [検針日](https://www.tepco.co.jp/pg/consignment/liberalization/kyoukyusya/change/retail/calendar.html) meter reading calendar including utility scripts to scrap data off the TEPCO web site

## Route B Service

- Apply online for the [Route B Service](https://www.tepco.co.jp/pg/consignment/liberalization/smartmeter-broute.html) -- this link is for TEPCO but there should be similar links for other providers
- You will receive an email from route_b_information@tepco.co.jp containing a 12-character password -- note that the embedded spaces are just there for readability and are not part of the password!
- Interestingly, you will only receive the 32-character user ID by post (same address as your billing address) -- why is this not the other way round is beyond me. Similarly note that the embedded spaces are just there for readability

## Hardware

- [M5StickC-PLUS2](https://www.switch-science.com/products/9350) - ESP32 controller with a nice color display and expandable I/O
- Note that the new board [M5StickS3](https://www.switch-science.com/products/10921) released in March 2026 is sadly pin-incompatible with Wi-SUN HAT (HAT2 is now 16-pin) It also lacks RTC, so may not be ideal for real-time energy tracking use cases
- [BP35A1](https://www.rohm.com/products/wireless-communication/specified-low-power-radio-modules/bp35a1-product#productDetail) -- Wi-SUN Compatible Wireless Module, EOL as of 2026 so only available while stock lasts
- [BP35C1-J11-T01]() -- alternative to BP35A1, evaluation board for the newer BP35C0-J11 module
- [Wi-SUN HAT rev0.2](https://booth.pm/ja/items/1650727) -- M5Stick HAT kit for the Wi-SUN module, make sure to buy the matching version for BP35A1 vs. BP35C1-J11-T01

---
TODO: update

## Software

### Clone this repository

```bash
git clone https://github.com/miyaichi/SmartMeter.git
cd SmartMeter
```

### Download Ambient module

```bash
curl -o ambient.py https://raw.githubusercontent.com/AmbientDataInc/ambient-python-lib/master/ambient.py
```

### Copy configuration file

```bash
cp SmartMeter.excample.json SmartMeter.json
```

### Configuration

#### SmartMeter.json

スマートメーター にアクセスするための「B ルート認証情報」と、利用状況確認のために使う「契約アンペア数」、月間利用状況確認のために使う「検針日」を設定します。また、Ambient にデータを送信するのであれば、Ambient でチャンネル ID を作成し、ライトキーと合わせて設定してください。

| Name              | Description               | Example                                                 |
| ----------------- | ------------------------- | ------------------------------------------------------- |
| id                | B ルート認証 ID           | "000000XXXXXX00000000000000XXXXXX"                      |
| password          | B ルート認証 I パスワード | "XXXXXXXXXXXX"                                          |
| contract_amperage | 契約アンペア数            | "50"                                                    |
| charge_func       | 電気料金計算関数名        | "tokyo_gas_1"                                           |
| collect_date      | 検針日                    | "22"                                                    |
| ambient           | Ambient のチャンネル情報  | {"channel_id": "XXXXX","write_key": "XXXXXXXXXXXXXXXX"} |

#### 電気料金計算

契約アンペアと検針日の情報があれば、おおよその電気料金を計算することができるので、charge.py で料金計算関数を定義できるようにしてあります。東京ガスの料金計算を実装してありますので、必要に応じて追加し、その関数名を SmartMeter.json の charge_func で指定してください（例: "charge_func": "tokyo_gas_1"）。関数の実装例は下記です。正確には各種割引とかあるのですが、変化量がわかればいいので、正確な実装ではありません。

```python
def tokyo_gas_1(contract, power):
    """
    TOKYO GAS「ずっとも電気1」での電気料金計算

    Parameters
    ----------
    contract : str
        契約アンペア数
    power : float
        前回検針後の使用電力量（kWh）

    Returns
    -------
    fee: int
        電気料金
    """
    fee = {'30': 858.00, '40': 1144.00, '50': 1430.00, '60': 1716.00}[contract]

    if power <= 140:
        fee += 23.67 * power
    elif power <= 350:
        fee += 23.67 * 140
        fee += 23.88 * (power - 140)
    else:
        fee += 23.67 * 140
        fee += 23.88 * 350
        fee += 26.41 * (power - 140 - 350)
    return int(fee)
```

#### Ambient

SmartMeter.json で Ambient のチャンネル情報を設定すると、30 秒に一度（1 日に 2,880 回 < Ambient の上限値 3,000）データを送信します。送信するデータと単位は以下の通りです。

| Name       | Unit | Description                              |
| ---------- | ---- | ---------------------------------------- |
| データー 1 | A    | 瞬時電流計測値(E8)                       |
| データー 2 | kW   | 瞬時電力計測値(E7)                       |
| データー 3 | kWh  | 当月（前回検針後）の積算電力量計測値(EA) |
| データー 4 | 円   | 当月（前回検針後）の電気料金             |

## Install

必要なファイルを M5StackC にコピーします。

/flash/apps/

- SMM.py

/flash/

- BP35A1.py
- ambient.py
- charge.py
- ntpdate.py
- SmartMeter.json

## Debug

ログレベル DEBUG でログが出力されています。M5StickC のシリアルに接続して、動作状況を確認してください。

```bash
screen /dev/tty.usbserial-00001214 115200
```

## Credit

- [M5StickC で家庭用スマートメーターをハックする！](https://kitto-yakudatsu.com/archives/7206)

- [B ルートやってみた - スカイリー・ネットワークス](http://www.skyley.com/products/b-route.html)

- [特定省電力無線モジュール BP35A1 スタートガイド](https://micro.rohm.com/jp/download_support/wi-sun/data/other/bp35a1-startguide_v150.pdf)

- [BP35A1 コマンドリファレンスマニュアル（SE 版）](https://rabbit-note.com/wp-content/uploads/2016/12/50f67559796399098e50cba8fdbe6d0a.pdf)

- [ECHONET 規格書 Version 3.21 （日本語版）/ APPENDIX ECHONET 機器オブジェクト詳細規定](https://echonet.jp/spec_g/#standard-02)
