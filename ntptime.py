try:
    import usocket as socket
except:
    import socket
try:
    import ustruct as struct
except:
    import struct

# Determine epoch automatically

import utime
if utime.gmtime(0)[0] == 2000:
    # NTP epoch (1900) -> MicroPython epoch (2000)
    NTP_DELTA = 3155673600
else:
    # NTP epoch (1900) -> Unix epoch (1970)
    NTP_DELTA = 2208988800

# The NTP host can be configured at runtime by doing: ntptime.host = 'myhost.org'
host = "jp.pool.ntp.org"

def time():
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA


# UIFlow 2 firmware comes with TZ support, use utime.gmtime instead of utime.localtime
def settime():
    t = time()
    import machine
    import utime

    tm = utime.gmtime(t)
    machine.RTC().datetime(
        (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
