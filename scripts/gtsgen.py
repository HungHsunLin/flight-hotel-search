"""生成 Google Hotels 的 ts 參數（純 protobuf 手刻，無外部依賴）"""
import base64, sys

def varint(n):
    o = b''
    while True:
        b_ = n & 0x7f; n >>= 7
        o += bytes([b_ | (0x80 if n else 0)])
        if not n: return o

def fld(num, wt): return varint((num << 3) | wt)
def vf(num, val): return fld(num, 0) + varint(val)          # varint field
def sf(num, s):                                              # string/nested field
    b_ = s.encode() if isinstance(s, str) else s
    return fld(num, 2) + varint(len(b_)) + b_

def date(y, m, d): return vf(1, y) + vf(2, m) + vf(3, d)

def _nights(ci, co):
    from datetime import date as D
    return (D(*ci[:3]) and (D(*co) - D(*ci)).days)

def make_ts(kgid, name, ci, co, adults=2, rooms=1, curr='TWD'):
    # 人數是「重複 field 1 的次數」，一位成人一組 {1:{1:3}}，不是把數字寫進某個欄位。
    # 之前誤把人數塞進 3.2.6，Google 完全忽略、一律回 2 人房價；實測比對瀏覽器產生的
    # ts 才發現真正的編碼在頂層 field 2，且靠重複次數表示人數。
    occupancy = sf(1, vf(1, 3)) * adults + vf(2, rooms)
    # 3.2.2.3 是住宿晚數（不是房間數）——同樣是比對瀏覽器 ts 才確認的。
    place = sf(2, sf(1, kgid) + sf(7, name)) + sf(3, b'')
    dates = sf(2, sf(1, date(*ci)) + sf(2, date(*co)) + vf(3, _nights(ci, co))) + sf(6, vf(1, 1))
    body  = sf(1, place) + sf(2, dates)
    tail  = sf(1, sf(7, curr)) + sf(3, b'')
    raw   = vf(1, 1) + sf(2, occupancy) + sf(3, body) + sf(5, tail)
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')

if __name__ == '__main__':
    kgid, name, ci, co = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    ad = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    # 幣別必須從這裡進 protobuf——URL 的 curr= 參數對 Hotels 無效（實測）。
    cur = sys.argv[6] if len(sys.argv) > 6 else 'TWD'
    p = lambda s: tuple(int(x) for x in s.split('-'))
    print(make_ts(kgid, name, p(ci), p(co), ad, 1, cur))
