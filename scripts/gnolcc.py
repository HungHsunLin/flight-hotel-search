"""排除廉航查來回機票——正確做法。

為什麼需要這支腳本（不要只用 gflight.sh 再自己過濾航空公司）：

Google Flights 搜尋結果那一頁，每一筆的資料裡**只有去程航段的航空公司**，價格是
「來回總價 X 起」——那個「起」是「配上最便宜的回程」算出來的下限，而最便宜的回程
通常就是廉航。所以拿搜尋結果過濾「航空公司不是廉航」，濾掉的只是去程；回程可能
是捷星、樂桃，而且會變成分段購票（兩張獨立票，行李不直掛、延誤互不負責）。

實測 TPE→KIX 一組來回日期：搜尋頁的「中華航空 NT$11,711」實際是中華去程 + 捷星
回程的混搭；真正兩段都是中華的來回票是 NT$13,819，差了 NT$2,108。

正解是把航空公司篩選塞進查詢字串——**Google 的航空公司篩選會同時套用到兩個航段**，
所以回來的價格保證整趟都是那家（或其聯營夥伴）。兩個限制：
  1. 必須用**當前語系介面**的航空公司名。hl=zh-TW 下 'China Airlines' 回 0 筆、
     '中華航空' 才有效；切到 hl=en 則反過來。各語系的名單在 locales.py 的
     full_service，切換語系時會自動跟著換。
  2. 一次只能一家。'中華航空 長榮航空' 會回 0 筆，所以只能逐家查再合併。

用法:
  gnolcc.py 臺北市 大阪 2026-03-15 2026-03-20
  gnolcc.py 臺北市 東京都 2026-11-15            # 單程
  gnolcc.py 臺北市 大阪 2026-03-15 2026-03-20 --airlines 中華航空 長榮航空
"""
import sys, os, argparse, urllib.parse, urllib.request
from datetime import date
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfparse, locales

LANG, L, CURR, REGION, UA = locales.from_env()

# 全服務航空名單（刻意不含任何廉航）隨語系走，見 locales.py 的 full_service。
# 想擴充（例如飛歐美要加漢莎、荷航）就往那裡加，名稱一律用**該語系介面**的寫法。
FULL_SERVICE = L['full_service']


def query(frm, to, dep, ret, airline):
    q = f'Flights from {frm} to {to} on {dep}'
    if ret:
        q += f' through {ret}'
    q += f' {airline}'
    p = urllib.parse.urlencode({'q': q, 'curr': CURR, 'hl': LANG, 'gl': REGION})
    req = urllib.request.Request(f'https://www.google.com/travel/flights?{p}',
                                 headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            page = r.read().decode('utf-8', 'ignore')
    except Exception:
        return []
    rows = gfparse.parse(page, LANG)
    for x in rows:
        x['filter'] = airline
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('frm'); ap.add_argument('to'); ap.add_argument('dep')
    ap.add_argument('ret', nargs='?')
    ap.add_argument('--airlines', nargs='+', default=FULL_SERVICE)
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()

    U = L['ui']
    if date(*[int(x) for x in a.dep.split('-')]) < date.today():
        print(U['past_date'].format(what=U['depart_date'], date=a.dep, today=date.today()),
              file=sys.stderr)
        print(U['past_hint'], file=sys.stderr)
        return 1

    trip = f'{a.dep} -> {a.ret}' if a.ret else U['oneway'].format(d=a.dep)
    print(f"{a.frm} -> {a.to}  {trip} | {U['per_airline'].format(n=len(a.airlines))}", flush=True)
    print(U['filter_note'] + '\n', flush=True)

    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(lambda al: query(a.frm, a.to, a.dep, a.ret, al), a.airlines))

    rows, seen = [], set()
    for got in res:
        for x in got:
            key = (x['airline'], x['dep'], x['price'])
            if key not in seen:
                seen.add(key); rows.append(x)
    if not rows:
        print(U['no_route'])
        return 1
    rows.sort(key=lambda r: r['price'])
    print(gfparse.render(rows, limit=a.top, lang=LANG, symbol=locales.symbol_for(CURR)))
    miss = [al for al, got in zip(a.airlines, res) if not got]
    if miss:
        print('\n' + U['no_flights_for'] + ', '.join(miss))
    return 0


if __name__ == '__main__':
    sys.exit(main())
