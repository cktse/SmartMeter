#
# ECHONET protocol message cracker
#
# Example messages were captured live from my home smart meter.
# Big caveat: it supports an older version of the spec (revision F) 
# Most of the github projects seems to also be coded wrt to the same revision F spec.
# The latest spec revision R as of 2026 has major incompatible changes.
#
import sys

# hex to unsigned int
def h2i(h):
    return int(h, 16)

# hex to signed short
def h2ss(h):
    assert(len(h)==4)
    s = int(h, 16)
    if s >= 0x8000:
        s -= 0x10000
    return s

# hex to signed long
def h2sl(h):
    assert(len(h)==8)
    s = int(h, 16)
    if s >= 0x80000000:
        s -= 0x100000000
    return s

# hex to int list (ascii bytes)
def h2l(h):
    return [int(h[i*2:i*2+2], 16) for i in range(len(h)>>1)]


# Raw Responses from Smart Meter 
xl = {
'D3': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201D30400000001',
'D5': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FF02:0000:0000:0000:0000:0000:0000:0001 0E1A 0E1A 001C6400601421A3 1 0012 108100000EF0010EF0017301D50401028801',
'D7': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000F 1081000102880105FF017201D70106',
'E0': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201E0040000FE73',
'E2': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6\
400601421A3 1 00D0 1081000102880105FF017201E2C2000B0000F7660000F7680000F76A0000F76C0000F76D0000F76F0000F7700000\
F7720000F7740000F7760000F7770000F7790000F77A0000F77C0000F77E0000F7800000F7810000F7830000F7840000F7860000F788000\
0F7890000F78B0000F78D0000F78E0000F7900000F7920000F7930000F7950000F7960000F7980000F79A0000F79C0000F79D0000F79F00\
00F7A00000F7A20000F7A40000F7A60000F7A70000F7A90000F7AB0000F7AD0000F7AF0000F7B00000F7B20000F7B40000F7B6',
'E7': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201E70400000278',
'E8': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201E804001E0032',
'EA': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0019 1081000102880105FF017201EA0B07EA05140E00000000FE68',
'EB': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0019 1081000102880105FF017201EB0B07EA0518161E0000000016',
'80': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000F 1081000102880105FF017201800130',
'81': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000F 1081000102880105FF017201810161',
'82': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201820400004600',
'83': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000E 1081000102880105FF0152018300',
'88': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000F 1081000102880105FF017201880142',
'8A': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0011 1081000102880105FF0172018A03000016',
'8D': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 001A 1081000102880105FF0172018D0C463234473336363530350000',
'97': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0010 1081000102880105FF01720197020E1A',
'98': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF017201980407EA0514',
'9C': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 000E 1081000102880105FF0152019C00',
'9D': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF0172019D0403808188',
'9E': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 0012 1081000102880105FF0172019E040381E5ED',
'9F': 'ERXUDP FE80:0000:0000:0000:021C:6400:6014:21A3 FE80:0000:0000:0000:021D:1290:0005:747B 0E1A 0E1A 001C6400601421A3 1 001F 1081000102880105FF0172019F111941414160404000624300414040430202',
}

if len(sys.argv[1]) == 2:
    x = xl[sys.argv[1]]
else:
    x = sys.argv[1]

# always 9 components, space-delimited
values = x.split(' ')
print(len(values)) # 9

(erxudp, source_ipv6, dest_ipv6, source_port, dest_port, mac_addr, one, data_len, data) = values

# 0: 'ERXUDP'
# 1: source IPv6, e.g. 'FE80:0000:0000:0000:021C:6400:6014:21A3'
# 2: dest IPv6, e.g. 'FE80:0000:0000:0000:021D:1290:0005:747B'
# 3: source port
# 4: dest port
# 5: MAC address
# 6: '1' always
# 7: length of data
# 8: data

print('Header:', erxudp)
print('Source:', source_ipv6, ':', h2i(source_port))
print('Dest  :', dest_ipv6, ':', h2i(dest_port))
print('MAC   :', mac_addr)
print('1     :', one)
print('Length:', h2i(data_len))
print('Data  : len(', int(len(data)/2), ')')

# Data is the Echonet Lite payload with the frame format:
# Echonet Lite電文構成(フレームフォーマット)によると
# EHD1 (1byte)
# EHD2 (1byte)
# TID (2bytes)
# ここからEDATA
# SEOJ: 送信元Echonet Liteオブジェクト指定 (3bytes)
# DEOJ: 送信先Echonet Liteオブジェクト指定 (3bytes)
# ESV: Echonet Liteサービス (1byte)
# OPC: 処理プロパティ数 (1byte)
# EPC: Echonet Liteプロパティ (1byte)
# PDC: EDTのバイト数 (1byte)
# EDT: プロパティ値データ (PDCで指定bytes)
ehd1  = data[0:0 + 2]
ehd2  = data[2:2 + 2]
tid   = data[4:4 + 4]
edata = data[8:]
seoj  = data[ 8: 8 + 6]
deoj  = data[14:14 + 6]
esv   = data[20:20 + 2]
opc   = data[22:22 + 2]
epc   = data[24:24 + 2]
pdc   = data[26:26 + 2]
edt   = data[28:]

print('\tSEOJ :', seoj)
print('\tDEOJ :', deoj)
print('\tESV  :', esv, 'OK' if esv[0]=='7' else 'NOT OK' if esv[0]=='5' else 'UNKNOWN')
print('\tOPC  :', opc)
print('\tEPC  :', epc)
print('\tPDC  :', pdc)
print('\tEDT  :', edt)

if pdc == 0:
    exit(0)

if epc == '80':
    # 動作状態
    # unsigned char
    status = edt[:2]
    print('80.status:', status)

elif epc == '81':
    # 設置場所
    # unsigned char
    loc = h2i(edt[:2])
    bitmap = '' 
    for i in range(7, -1, -1):
        bitmap += str(((loc >> i) & 1))
    free = bitmap[0]
    loc_code = bitmap[1:1 + 4]
    loc_num  = bitmap[5:]
    loc_text = [
        None,
        '居間、リビング',
        '食堂、ダイニング',
        '台所、キッチン', 
        '浴室、バス',
        'トイレ', 
        '洗面所、脱衣所',
        '廊下',
        '部屋',
        '階段',
        '玄関',
        '納戸',
        '庭、外周',
        '車庫', 
        'ベランダ、バルコニー', 
        'その他',
    ]
    
    print('81.location:', loc, free, loc_code, loc_num, 'UNDEFINED' if loc == 255 else 'FREE' if free == '1' else loc_text[int(loc_code, 2)])

elif epc == '82':
    # 規格 Version 情報
    # unsigned char×4
    reserved_1 = edt[ :2]
    reserved_2 = edt[2:2 + 2]
    release    = chr(h2i(edt[4:4 + 2]))
    revision   = edt[6:]
    print('82.version:', reserved_1, reserved_2, release, revision)
    
elif epc == '88':
    # 異常発生状態
    # unsigned char
    error_code = edt[:2]
    error_text = 'YES' if error_code == '41' else 'NO' if error_code == '42' else 'UNKNOWN'
    print('88.abnormal:', error_code, error_text)

elif epc == '8A':
    # メーカコード
    # unsigned char×3
    # https://echonet.jp/wp/wp-content/uploads/pdf/General/Echonet/ManufacturerCode/list_code.pdf
    # e.g. 000016 = 株式会社東芝
    maker = edt[:6]
    print('8A.maker:', maker)

elif epc == '8D':
    # 製造番号
    # 12-byte ascii
    serial = bytes.fromhex(edt).decode('ascii')
    print('8D.serial:', serial)

elif epc in ['9D', '9E', '9F']:
    # Property Map
    p_count = h2i(edt[:2])
    p_raw   = edt[2:]
    epcs = []
    if p_count <= 10:
        # format 1 (list)
        for i in range(p_count):
            epcs.append(p_raw[i*2:i*2 + 2])
    else:
        # format 2 (bitmap)
        byte_list = h2l(p_raw)
        for i, byte in enumerate(byte_list):
            print(i, byte)
            for bit in range(8):
                if byte & (1 << bit):
                    m_epc = ((bit + 8) << 4) | i
                    epcs.append(m_epc)
        epcs = list(map(lambda n: f'{n:X}', sorted(epcs)))
    print(f'{epc}.properties:', p_count, epcs)
    assert(p_count == len(epcs))

elif epc == 'E2':
    # E2 historical query of cumulative energy in 30mins interval (day set via E5)
    # unsigned short = historical data as of N days from today 
    # unsigned long x48 = 24x2 30mins in the day from 00:00 to 23:30
    n = h2i(data[:2])
    e = [h2i(data[2+i*8:2+(i+1)*8]) for i in range(0, 48)]
    print('E2.n:', n)
    print('E2.e:', e)

elif epc == 'E7':
    # E7 Measured instantaneous electric energy
    # signed long
    e = h2sl(edt[:8])
    print(e)

elif epc == 'E8':
    # E8 Measured instantaneous currents
    # signed short x2
    r = h2ss(edt[:4])
    t = h2ss(edt[4:])
    if r == 0x7FFE:
        r = 0
    if t == 0x7FFE:
        t = 0
    print(f'E8: r:{r/10.0} + t:{t/10.0} = {(r+t)/10.0}')

elif epc in ['EA', 'EB']:
    # Cumulative amounts of electric energy measured at fixed time
    # EA=normal direction; EB=reverse direction
    # unsigned short + unsigned char×2 + unsigned char×3 + unsigned long
    year = h2i(edt[:4])
    date = h2l(edt[4:14])
    en_t = h2i(edt[14:])
    print(f'{epc}:', (year, date[0], date[1], date[2], date[3], date[4]), en_t)
