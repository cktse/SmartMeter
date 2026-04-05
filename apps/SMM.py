#
# SMM.py  –  Smart Meter Monitor for M5StickC Plus2
# UIFlow 2.x  (import M5 / from M5 import *)
#
# Display object  : M5.Lcd  (aliased as Display via "from M5 import *")
#   • M5.Lcd and Display refer to the same M5GFX object.
#   • Font constants: M5.Lcd.FONTS.DejaVu9 / DejaVu12 / DejaVu18 / DejaVu24
#   • Key drawing calls used here:
#       Display.setFont(M5.Lcd.FONTS.DejaVuXX)
#       Display.setTextColor(fgcolor=0xRRGGBB, bgcolor=0xRRGGBB)
#       Display.setCursor(x, y)
#       Display.getCursor() -> (x,y)
#       Display.print(text)
#       Display.textWidth(text)          – pixel width with current font
#       Display.fillRect(x, y, w, h, color)
#       Display.setRotation(r)           – 1=landscape, 3=landscape-flip
#       Display.clear(color)
#

import M5
from M5 import *          # exports: Display, BtnA, BtnB, Widgets, …
import machine
import ujson
import utime
import ntptime
import network
import logging
import charge
from BP35A1 import BP35A1
##from mock_BP35A1 import BP35A1

# ---------------------------------------------------------------------------
# Global variables
# ---------------------------------------------------------------------------
level        = logging.DEBUG   # Log level
bp35a1       = None            # BP35A1 object
config       = {}              # Configuration dict
rotation     = 1               # 1=LANDSCAPE  3=LANDSCAPE_FLIP  (M5GFX)
logger       = None            # Logger object
logger_name  = 'SMM'           # Logger name
ambient_client = None          # Ambient instance
max_retries  = 30              # Maximum consecutive failures before reset
_wifi_sta    = None            # WLAN STA interface

# ---------------------------------------------------------------------------
# Colormap (tab10) — identical to original
# ---------------------------------------------------------------------------
colormap = (
    0x1f77b4,  # tab:blue
    0xff7f0e,  # tab:orange
    0x2ca02c,  # tab:green
    0xd62728,  # tab:red
    0x9467bd,  # tab:purple
    0x8c564b,  # tab:brown
    0xe377c2,  # tab:pink
    0x7f7f7f,  # tab:gray
    0xbcbd22,  # tab:olive
    0x17becf,  # tab:cyan
)
bgcolor = 0x000000   # Background color
uncolor = 0xa9a9a9   # Label / unit color
color1  = colormap[0]  # Instantaneous value color (blue)
color2  = colormap[1]  # Monthly total color        (orange)

# ---------------------------------------------------------------------------
# Font helpers
#
# UIFlow 2 font constants (confirmed from official docs):
#   M5.Lcd.FONTS.DejaVu9   ≈  9 px tall
#   M5.Lcd.FONTS.DejaVu12  ≈ 12 px tall
#   M5.Lcd.FONTS.DejaVu18  ≈ 18 px tall
#   M5.Lcd.FONTS.DejaVu24  ≈ 24 px tall
#
# These replace the UIFlow-1 lcd.FONT_DefaultSmall / lcd.FONT_Ubuntu /
# lcd.FONT_DejaVu24 constants.
# ---------------------------------------------------------------------------
# Convenience aliases – resolved lazily at runtime once M5.begin() has run
def _FONT_TINY():   return M5.Lcd.FONTS.DejaVu12
def _FONT_SMALL():  return M5.Lcd.FONTS.DejaVu18
def _FONT_MEDIUM(): return M5.Lcd.FONTS.DejaVu24
def _FONT_LARGE():  return M5.Lcd.FONTS.DejaVu40

# Approximate pixel heights (used for manual layout arithmetic)
_H_SMALL  = 18
_H_MEDIUM = 24
_H_LARGE  = 40

# M5StickC Plus2 screen in landscape: 240 x 135 px
_SCREEN_W = 240
_SCREEN_H = 135

# ---------------------------------------------------------------------------
# Button A callback – flip screen orientation
# ---------------------------------------------------------------------------
def _btnA_pressed(_):
    global rotation
    rotation = 3 if rotation == 1 else 1
    Display.setRotation(rotation)
    Display.clear(bgcolor)
    if logger:
        logger.info('Set screen rotation: %d', rotation)

# ---------------------------------------------------------------------------
# Wi-Fi helpers  (replaces UIFlow-1 wifiCfg module)
# ---------------------------------------------------------------------------
def _wifi_init():
    """Activate the STA interface; UIFlow 2 firmware reconnects automatically
    using credentials stored in NVS (configured once via M5Burner)."""
    global _wifi_sta
    _wifi_sta = network.WLAN(network.STA_IF)
    _wifi_sta.active(True)

def _wifi_is_connected():
    return _wifi_sta is not None and _wifi_sta.isconnected()

def checkWiFi(_=None):
    """Periodic watchdog – called by machine.Timer every 60 s."""
    if not _wifi_is_connected():
        if logger:
            logger.warn('Wi-Fi lost – attempting reconnect')
        # Toggling active() triggers the NVS-credential auto-connect path
        _wifi_sta.active(False)
        utime.sleep_ms(500)
        _wifi_sta.active(True)
        for _ in range(20):          # wait up to 10 s
            if _wifi_sta.isconnected():
                return
            utime.sleep_ms(500)
        machine.reset()              # give up and reboot

# ---------------------------------------------------------------------------
# Status / progress display
# ---------------------------------------------------------------------------
def status(message):
    logger.debug('STATUS: ' + message)
    """One-line status string centred in the middle of the screen."""
    x, y, w, h = 3, 34, 154, _H_SMALL + 2
    Display.fillRect(x, y, w, h, bgcolor)
    if logger:
        logger.info(message)
    Display.setFont(_FONT_SMALL())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    tw = Display.textWidth(message)
    Display.setCursor(x + max(0, (w - tw) // 2), y)
    Display.print(message)


def progress(percent):
    """Horizontal progress bar at the bottom of the screen."""
    w  = _SCREEN_W
    h  = _SCREEN_H
    bw = (w - 6) * percent // 100
    Display.fillRect(3,      h - 12, bw,          12, color1)
    Display.fillRect(3 + bw, h - 12, w - 6 - bw,  12, bgcolor)
    Display.setFont(_FONT_TINY())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    label = '{}%'.format(percent)
    tw = Display.textWidth(label)
    Display.setCursor((w - tw) // 2, h - 10)
    Display.print(label)

# ---------------------------------------------------------------------------
# Instantaneous readings
# ---------------------------------------------------------------------------
def instantaneous_amperage(amperage):
    """Current amperage – top-left """
    x, y, w, h = 3, 3, 113, 47
    Display.fillRect(x, y, w, h, bgcolor)

    # Large numeric value
    amp_str = str(int(amperage))
    Display.setFont(_FONT_LARGE())            # DejaVu40
    Display.setTextColor(fgcolor=color1, bgcolor=bgcolor)
    tw = Display.textWidth(amp_str)
    Display.setCursor(x + 51 - tw, y + 5)
    Display.print(amp_str)

    # 'A' unit suffix (small, baseline-aligned)
    Display.setFont(_FONT_SMALL())            # DejaVu18
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    Display.setCursor(Display.getCursor()[0], y + (h - _H_SMALL))
    Display.print('A')

    # Contract amperage (medium size)
    contract_str = str(int(config['contract_amperage']))
    Display.setFont(_FONT_MEDIUM())           # DejaVu24
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    Display.setCursor(x + 65, y + (h - _H_MEDIUM))
    Display.print(contract_str)

    # 'A' suffix for contract value
    Display.setFont(_FONT_SMALL())
    Display.setCursor(Display.getCursor()[0], y + (h - _H_SMALL))
    Display.print('A')


def instantaneous_power(power_kw):
    """Instantaneous power – top-right """
    x, y, w, h = 116, 3, 124, 47
    Display.fillRect(x, y, w, h, bgcolor)

    pw_str = str(int(power_kw))
    Display.setFont(_FONT_LARGE())
    Display.setTextColor(fgcolor=color1, bgcolor=bgcolor)
    tw = Display.textWidth(pw_str)
    # Right-align, reserving ~20 px for 'kW' suffix
    Display.setCursor(x + w - 20 - tw, y + 5)
    Display.print(pw_str)

    Display.setFont(_FONT_SMALL())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    Display.setCursor(Display.getCursor()[0], y + (h - _H_SMALL))
    Display.print('W')

# ---------------------------------------------------------------------------
# Monthly readings
# ---------------------------------------------------------------------------
def collect_range(collect, update):
    """Billing-period date range centred below the top strip."""
    x, y, w, h = 3, 50, 237, 25
    Display.fillRect(x, y, w, h, bgcolor)

    s = '{}~{}'.format(collect[5:10], update[5:10])
    Display.setFont(_FONT_SMALL())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    tw = Display.textWidth(s)
    Display.setCursor(x + (w - tw) // 2, y + 5)
    Display.print(s)


def monthly_power(power_kwh):
    """Monthly energy total – lower-left """
    x, y, w, h = 3, 75, 107, 60
    Display.fillRect(x, y, w, h, bgcolor)

    kwh_str = str(int(power_kwh))
    Display.setFont(_FONT_LARGE())
    Display.setTextColor(fgcolor=color2, bgcolor=bgcolor)
    tw = Display.textWidth(kwh_str)
    Display.setCursor(x + w - tw - 15, y + 5)
    Display.print(kwh_str)

    Display.setFont(_FONT_SMALL())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    tw2 = Display.textWidth('kWh')
    Display.setCursor(x + w - tw2 - 15, y + 40)
    Display.print('kWh')


def monthly_fee(fee):
    """Estimated monthly electricity cost – lower-right."""
    x, y, w, h = 110, 75, 130, 60
    Display.fillRect(x, y, w, h, bgcolor)

    fee_str = str(int(fee))
    Display.setFont(_FONT_LARGE())
    Display.setTextColor(fgcolor=colormap[1], bgcolor=bgcolor)
    tw = Display.textWidth(fee_str)
    Display.setCursor(x + w - tw, y + 5)
    Display.print(fee_str)

    Display.setFont(_FONT_SMALL())
    Display.setTextColor(fgcolor=uncolor, bgcolor=bgcolor)
    tw2 = Display.textWidth('Yen')
    Display.setCursor(x + w - tw2, y + 40)
    Display.print('Yen')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    try:
        # -- Initialise M5 hardware (display, buttons, power, IMU ...) -------
        M5.begin()

        # -- Logger -----------------------------------------------------------
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

        # -- Display ----------------------------------------------------------
        Display.setRotation(rotation)          # 1 = landscape
        Display.clear(bgcolor)
        Display.setFont(_FONT_SMALL())
        Display.setTextColor(fgcolor=0xFFFFFF, bgcolor=bgcolor)

        # -- Button A: flip orientation ---------------------------------------
        # UIFlow 2 button API:
        #   BtnA.setCallback(type=BtnA.CB_TYPE.WAS_PRESSED, cb=function)
        BtnA.setCallback(type=BtnA.CB_TYPE.WAS_PRESSED, cb=_btnA_pressed)

        # -- Wi-Fi ------------------------------------------------------------
        status('Connecting Wi-Fi')
        _wifi_init()
        # Firmware auto-connects from NVS credentials; poll up to 30 s
        for _t in range(30):
            if _wifi_is_connected():
              break
            utime.sleep(1)
        if not _wifi_is_connected():
            raise Exception('Cannot connect to WiFi.')

        # Periodic watchdog (every 60 s)
        #machine.Timer(0).init(
        #    period=60 * 1000,
        #    mode=machine.Timer.PERIODIC,
        #    callback=checkWiFi,
        #)

        # -- NTP time sync ----------------------------------------------------
        status('Set Time')
        ntptime.settime()

        # -- Load configuration -----------------------------------------------
        status('Load configuration')
        config_file = '/flash/SmartMeter.json'
        with open(config_file) as f:
            config = ujson.load(f)
        for key in ('id', 'password', 'contract_amperage',
                    'collect_date', 'charge_func'):
            if key not in config:
                raise Exception('{} is not defined in SmartMeter.json'.format(key))
        if 'ambient' in config:
            for key in ('channel_id', 'write_key'):
                if key not in config['ambient']:
                    raise Exception(
                        '{} is not defined in SmartMeter.json'.format(key))

        mday_calendar_file = 'calendar_' + str(utime.localtime()[0]) + '.json' # 検針日カレンダーフ>ァイル名
        try:
            with open(mday_calendar_file, 'r') as f:
                config_cal = ujson.load(f)
            logger.info('calendar file is founded !')
            config.update(config_cal) # 基本設定と検針日カレンダーを結合
        except FileNotFoundError:
            logger.info('calendar file is NOT founded !')

        if not isinstance(config['collect_date'], list):
            config['collect_date'] = [int(config['collect_date'])]*13  # backward compatibility
        config['collect_date'][0] = config['collect_date'][12]
        logger.info('collect_date: %s', collect_date)

        # -- Create objects ---------------------------------------------------
        status('Create objects')
        bp35a1 = BP35A1(
            config['id'],
            config['password'],
            int(config['contract_amperage']),
            config['collect_date'],
            progress_func=progress,
            logger_name=logger_name,
        )
        logger.info('BP35A1 config: (%s, %s, %s, %s)',
                    config['id'], config['password'],
                    config['contract_amperage'], config['collect_date'])

        # Renamed to avoid shadowing the imported `charge` module
        charge_func = eval('charge.{}'.format(config['charge_func']))
        logger.info('charge function: %s', charge_func.__name__)

        if 'ambient' in config:
            import ambient
            ambient_client = ambient.Ambient(
                config['ambient']['channel_id'],
                config['ambient']['write_key'],
            )
            logger.info('Ambient config: (%s, %s)',
                        config['ambient']['channel_id'],
                        config['ambient']['write_key'])

        # -- Connect to Smart Meter -------------------------------------------
        status('Connecting SmartMeter')
        (channel, pan_id, mac_addr, lqi) = bp35a1.open()
        logger.info('Connected. BP35A1 info: (%s, %s, %s, %s)',
                    channel, pan_id, mac_addr, lqi)

        # -- Monitoring loop --------------------------------------------------
        status('Start monitoring')
        amperage  = power_kw = power_kwh = amount = 0
        update    = collect = 'YYYY-MM-DD hh:mm:ss'
        retries   = 0
        t         = 0

        while retries < max_retries:
            # Process button callbacks and internal UIFlow 2 housekeeping
            M5.update()

            # Every 10 s – instantaneous readings
            if t % 10 == 0:
                try:
                    (_, amperage)      = bp35a1.instantaneous_amperage()
                    (update, power_kw) = bp35a1.instantaneous_power()
                    instantaneous_amperage(amperage)
                    instantaneous_power(power_kw)
                    retries = 0
                except Exception as e:
                    logger.exception(e)
                    retries += 1

            # Every 60 s – monthly totals
            if t % 60 == 0:
                try:
                    (collect, power_kwh) = bp35a1.monthly_power()
                    amount = charge_func(config['contract_amperage'], power_kwh)
                    collect_range(collect, update)
                    monthly_power(power_kwh)
                    monthly_fee(amount)
                    retries = 0
                except Exception as e:
                    logger.exception(e)
                    retries += 1

            # Every 30 s – send to Ambient
            if t % 30 == 0:
                try:
                    if ambient_client:
                        result = ambient_client.send({
                            'd1': amperage,
                            'd2': power_kw,
                            'd3': power_kwh,
                            'd4': amount,
                        })
                        if result.status_code != 200:
                            raise Exception(
                                'ambient.send() failed, status: %s'
                                % result.status_code)
                        retries = 0
                except Exception as e:
                    logger.exception(e)
                    retries += 1

            # Every 1 h – keep-alive ping
            if t % 3600 == 0:
                bp35a1.skPing()

            utime.sleep(1)
            t = utime.time()

    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print('ERROR:', e)
    finally:
        machine.reset()

