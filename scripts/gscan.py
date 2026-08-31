"""掃日期區間找最便宜的出發日 / 入住日。

用法:
  gscan.py flight TPE TYO 2026-10-01 2026-10-31 --nights 4
  gscan.py hotel  東京   2026-10-01 2026-10-31 --nights 3

語系/幣別/地區用環境變數控制（預設 zh-TW / TWD / tw）：
  GFH_LANG=en GFH_CURR=USD gscan.py hotel Kanazawa 2026-11-20 2026-11-30 --nights 2

對每個候選日期各發一次請求（並行），回傳依價格排序的日期清單。
並行度限制為 6，作為對來源網站的禮貌性節流，避免造成負擔；
壓低並行也讓結果更穩定，不會拿到一堆空結果卻誤以為「那天沒航班」。
"""
import sys, os, argparse, urllib.parse, urllib.request, statistics
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfparse, ghparse, gtsgen, locales

LANG, L, CURR, REGION, UA = locales.from_env()
U = L['ui']
SYM = locales.symbol_for(CURR)
WORKERS = 6


def get(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f'{url}?{q}', headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


def d(s): return date(*[int(x) for x in s.split('-')])


def scan_flight(frm, to, day, nights):
    ret = day + timedelta(days=nights)
    q = f'Flights from {frm} to {to} on {day} through {ret}'
    rows = gfparse.parse(get('https://www.google.com/travel/flights',
                             {'q': q, 'curr': CURR, 'hl': LANG, 'gl': REGION}), LANG)
    if not rows:
        return None
    b = rows[0]
    stop = U['nonstop'] if b['stops'] else U['connecting']
    return {'out': str(day), 'back': str(ret), 'price': b['price'],
            'detail': f"{b['airline']} {b['dep']}-{b['arr']} {stop}", 'n': len(rows)}


def scan_hotel(place, day, nights):
    out = day + timedelta(days=nights)
    # 幣別必須進 ts——URL 的 curr= 對 Hotels 無效（實測），少傳就固定回 TWD。
    ts = gtsgen.make_ts('', '', (day.year, day.month, day.day),
                        (out.year, out.month, out.day), adults=2, curr=CURR)
    rows = ghparse.parse(get('https://www.google.com/travel/search',
                             {'q': L['hotel_query'].format(place=place), 'hl': LANG,
                              'gl': REGION, 'curr': CURR, 'ts': ts}), LANG)
    if not rows:
        return None
    # 超出可訂範圍時 Google 靜默回「明天住一晚」的行情，頁面完全正常。把它當有效資料
    # 會直接汙染中位數排序——那份排行看起來合理但整個是錯的。寧可少一個日期。
    # 落掉的日期會併進結尾的 throttle_warn，那句話同時提到限流與可訂範圍兩種可能。
    if rows[0]['nights'] and rows[0]['nights'] != nights:
        return None
    med = int(statistics.median([r['price'] for r in rows]))
    b = rows[0]
    # 用中位數當排序鍵而非最低價：最低價常是青旅/膠囊，某天冒出一間便宜床位
    # 會讓那天看起來最划算，但整體行情其實很貴。中位數才反映「那天好不好訂」。
    return {'out': str(day), 'back': str(out), 'price': med, 'low': b['price'],
            'detail': f"{U['lowest']} {SYM}{b['price']:,} {b['name'][:20]}", 'n': len(rows)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['flight', 'hotel'])
    p.add_argument('args', nargs='+')
    p.add_argument('--nights', type=int, default=3)
    p.add_argument('--top', type=int, default=10)
    a = p.parse_args()

    if a.mode == 'flight':
        frm, to, start, end = a.args[0], a.args[1], a.args[2], a.args[3]
        job = lambda day: scan_flight(frm, to, day, a.nights)
        title = f"{frm}->{to} {U['stay_flight'].format(n=a.nights)}"
    else:
        place, start, end = a.args[0], a.args[1], a.args[2]
        job = lambda day: scan_hotel(place, day, a.nights)
        title = f"{place} {U['stay_hotel'].format(n=a.nights)}"

    if d(start) < date.today():
        # 查過去的日期，Google 就是安靜地回空結果，跟「地名打錯」「被限流」長得
        # 一模一樣——沒這個檢查，呼叫端會以為腳本壞了，繞一大圈去除錯，其實只是
        # 日期選錯年份（常見於「2月初」這種沒講年份、又已經過了今年那個月的說法）。
        print(U['past_date'].format(what=U['start_date'], date=start, today=date.today()),
              file=sys.stderr)
        print(U['past_hint'], file=sys.stderr)
        return 1

    days = []
    cur, last = d(start), d(end)
    while cur <= last:
        days.append(cur); cur += timedelta(days=1)

    print(U['scanning'].format(title=title, start=start, end=end, n=len(days), w=WORKERS),
          flush=True)
    if a.mode == 'hotel':
        print(U['scan_hotel_note'], flush=True)
    print(flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = [r for r in ex.map(job, days) if r]

    if not res:
        print(U['scan_empty']); return 1
    res.sort(key=lambda r: r['price'])
    label = U['depart_col'] if a.mode == 'flight' else U['checkin_col']
    pcol = U['price'] if a.mode == 'flight' else U['median_col']
    # 依顯示寬度對齊，不是字元數——中日文欄名佔 2 格，用 :<4 會整排跑掉。
    P = locales.dpad
    print(f"{P(U['rank'], 5)} {P(pcol, 11, '>')}  {P(label, 12)} "
          f"{P(U['return_col'], 12)} {U['content_col']}")
    print('-' * 76)
    for i, r in enumerate(res[:a.top], 1):
        print(f"{P(str(i), 5)} {P(SYM + format(r['price'], ','), 11, '>')}  "
              f"{P(r['out'], 12)} {P(r['back'], 12)} {r['detail']}")
    v = [r['price'] for r in res]
    print(f"\n{U['dates_with_data'].format(ok=len(res), all=len(days))} | "
          f"{U['lowest']} {SYM}{min(v):,} | {U['highest']} {SYM}{max(v):,} | "
          f"{U['spread']} {SYM}{max(v)-min(v):,}")
    if len(res) < len(days):
        print(U['throttle_warn'].format(n=len(days)-len(res)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
