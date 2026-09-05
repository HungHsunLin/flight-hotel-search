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
  1. 一次只能一家。'中華航空 長榮航空' 會回 0 筆，所以只能逐家查再合併。
  2. 名稱**用該語系介面的寫法最保險**，但別把它當硬規則——舊版文件宣稱
     「hl=zh-TW 下 'China Airlines' 回 0 筆」，實測是錯的（2026-09-02，
     臺北市->熊本市，跑 4 次得 5/5/5/0 筆）。那個 0 是下面說的間歇性回空，
     寫文件的人只測一次就撞上了。各語系名單在 locales.py 的 full_service。

還有一個更根本的坑：**同一句查詢重跑，結果會飄**。實測 TPE->KMJ 加中華航空跑 11 次，
有 2 次回 0 筆（約 18%），而此時換一句「已知有效」的查詢當對照組是會過的——也就是說
對照組分辨不出間歇性回空。要下「這家沒飛」的結論前，必須重跑**同一句** 2-3 次。

用法:
  gnolcc.py 臺北市 大阪 2026-03-15 2026-03-20
  gnolcc.py 臺北市 東京都 2026-11-15            # 省略回程日（**這不是單程票**！Google 會
                                                #  自己配一個預設回程並按來回計價，
                                                #  見 SKILL.md〈省略回程日不會查到單程票〉）
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
    """回 {'rows', 'title', 'error'}。

    刻意不把例外壓成空清單：網路失敗與「這家沒飛」長得一模一樣，混在一起就是
    這個 skill 一路在抓的那種靜默失敗。title 則是 0 筆時判斷查詢有沒有被解析的
    唯一線索，見 gfparse.page_title。
    """
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
    except Exception as e:
        return {'rows': [], 'title': '', 'error': f'{type(e).__name__}: {e}', 'dropped': {}}
    dropped = {}
    rows = gfparse.parse(page, LANG, dropped)
    for x in rows:
        x['filter'] = airline
    return {'rows': rows, 'title': gfparse.page_title(page), 'error': None, 'dropped': dropped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('frm'); ap.add_argument('to'); ap.add_argument('dep')
    ap.add_argument('ret', nargs='?')
    ap.add_argument('--airlines', nargs='+', default=None)
    ap.add_argument('--eu', action='store_true',
                    help='改用歐美線的全服務航空名單（中東樞紐＋歐洲本地）。'
                         '預設名單只有亞洲航空，查歐美線會漏掉最便宜的選項。')
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()
    if a.airlines is None:
        a.airlines = L.get('full_service_eu', FULL_SERVICE) if a.eu else FULL_SERVICE

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
        for x in got['rows']:
            key = (x['airline'], x['dep'], x['price'])
            if key not in seen:
                seen.add(key); rows.append(x)

    # 逐家查詢各自的丟棄統計要合併起來。這在「篩選單一航空卻回 0 筆」時最關鍵——
    # 實測查 ANA 東京→札幌，62 筆航班全部「無法取得總價」被丟光，輸出只剩「(無資料)」，
    # 而那則訊息列的四個原因沒有一個是真的。
    dropped = {}
    for got in res:
        for k, v in got.get('dropped', {}).items():
            dropped[k] = dropped.get(k, 0) + v

    failed = [(al, got['error']) for al, got in zip(a.airlines, res) if got['error']]
    if not rows:
        if dropped:
            detail = '、'.join(f'{k} {v}' for k, v in sorted(dropped.items(), key=lambda kv: -kv[1]))
            print(U['dropped_no_price'].format(n=sum(dropped.values()), detail=detail) + '\n')
        print(U['no_route'])
        # 全空時最該看的就是 Google 把查詢解析成什麼——同一句查詢每家都一樣，取第一個非空的。
        title = next((g['title'] for g in res if g['title']), '')
        if title:
            print(U['resolved_as'].format(title=title))
        for al, err in failed:
            print(U['query_failed'].format(airline=al, error=err), file=sys.stderr)
        return 1
    rows.sort(key=lambda r: r['price'])
    print(gfparse.render(rows, limit=a.top, lang=LANG, symbol=locales.symbol_for(CURR),
                         dropped=dropped))

    miss = [al for al, got in zip(a.airlines, res) if not got['rows'] and not got['error']]
    if miss:
        print('\n' + U['no_flights_for'] + ', '.join(miss))
    for al, err in failed:
        print(U['query_failed'].format(airline=al, error=err), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
