"""解析 Google Flights 搜尋結果頁。可當 CLI（吃 stdin）或 import 用。

語系由 locales.py 提供的語言包決定。不帶語系時走 zh-TW，與加入多語支援前的行為一致。
CLI 用 --lang 指定，或設環境變數 GFH_LANG。
"""
import sys, os, re, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locales


def page_title(page):
    """回傳頁面的 <title>。

    這是 0 筆結果時唯一能分辨「真的沒航班」與「Google 根本沒把查詢字串解析成一條
    航線」的線索，實測三態（見 SKILL.md 的「0 筆不等於沒航班」）：
      臺北到熊本市 | Google 航班/機票   解析成功
      臺北到熊本縣 | 探索               解析成行政區，Flights 查不了縣層級 -> 0 筆
      搜尋全球便宜航班並預訂機票 - ...   整句沒被解析，退回首頁 -> 0 筆
    刻意不拆解成出發地/目的地：拆解得綁死語系，原樣印出反而三種語系都自我說明。
    """
    m = re.search(r'<title[^>]*>(.*?)</title>', page, re.S)
    return html.unescape(m.group(1)).strip() if m else ''


def parse(page, lang=None, dropped=None):
    """回傳 [{price, airline, dep, arr, dep_apt, arr_apt, stops, duration}]，依價格排序。

    dropped：可選的 dict，收集「有航班列、但 Google 沒給票價」的航空公司計數。
    這些列以前被靜默丟棄，導致**整家航空可以從結果裡消失而毫無跡象**——實測
    東京都→札幌市，ANA 共 38 班的 aria-label 全部以「無法取得總價」開頭，
    解析結果裡一筆 ANA 都沒有，而羽田–新千歲是日本最繁忙航線之一。
    傳一個 dict 進來就能把它們撈出來示警。見 SKILL.md〈第五種 0 筆〉。
    """
    _, L = locales.resolve(lang)
    F = L['flight']
    lo, hi = L['label_len']
    rows, seen = [], set()

    for m in re.findall(r'aria-label="([^"]{%d,%d}?)"' % (lo, hi), page):
        s = html.unescape(m)
        if F['marker'] not in s:
            continue

        # 價格是強過濾條件：抓不到就不是航班列。價格樣式逐條試，因為幣別會隨 curr
        # 改變（zh-TW 配 JPY 會變「日圓」），寫死單一幣別名在換幣時會整批漏掉。
        price = None
        for pat in F['price']:
            pm = re.search(pat, s)
            if pm:
                price = int(pm.group(1).replace(',', ''))
                break
        if price is None:
            # 注意這不代表「這列不是航班」——原註解那個假設是錯的。Google 對某些
            # 航段就是不提供票價，航班本身存在。沒價格無從比價所以照舊不列入，
            # 但一定要記下來，否則使用者會看到一個沒有 ANA 的東京→札幌清單。
            if dropped is not None:
                am = re.search(F['airline'], s)
                if am:
                    k = am.group(1).strip()
                    dropped[k] = dropped.get(k, 0) + 1
            continue

        am = re.search(F['airline'], s)
        rm = re.search(F['route'], s)
        if not (am and rm):
            continue
        g = rm.groupdict()

        key = (am.group(1), g['dep'], price)
        if key in seen:
            continue
        seen.add(key)

        dm = re.search(F['duration'], s)
        rows.append({
            'price': price,
            'airline': am.group(1).strip(),
            'dep': g['dep'].strip(), 'arr': g['arr'].strip(),
            'dep_apt': locales.airport_code(g['dep_apt']),
            'arr_apt': locales.airport_code(g['arr_apt']),
            'stops': F['nonstop'] in s,
            'duration': dm.group(1).strip() if dm else '',
        })

    rows.sort(key=lambda r: r['price'])
    return rows


def render(rows, limit=12, lang=None, symbol=None, title='', dropped=None):
    _, L = locales.resolve(lang)
    U = L['ui']
    sym = symbol or L['symbol']

    # 丟棄示警放在**最前面**：它說的是「有東西不見了」，比結尾那句「還有更多沒印」
    # 危險得多，而印在 12 行資料後面等於沒印（同 ghparse.py 的既有原則）。
    # 0 筆時尤其要印——那正是最容易被誤判成「限流」或「沒航班」的情況。
    warn = ''
    if dropped:
        detail = '、'.join(f'{k} {v}' for k, v in sorted(dropped.items(), key=lambda kv: -kv[1]))
        warn = U['dropped_no_price'].format(n=sum(dropped.values()), detail=detail) + '\n\n'

    if not rows:
        # 把 Google 自己的解析結果攤在失敗現場。原本只列三個可能原因，要讀者
        # 另外做實驗去分辨；title 一直帶著答案，只是沒人去看。
        msg = U['no_data_flight']
        if title:
            msg += '\n' + U['resolved_as'].format(title=title)
        return warn + msg

    P = locales.dpad
    out = [f"{P(U['price'], 11, '>')}  {P(U['airline'], 14)} {P(U['outbound'], 19)} "
           f"{P(U['route'], 9)} {P(U['stops'], 6)} {U['duration']}", '-' * 78]
    for r in rows[:limit]:
        route = f"{r['dep_apt']}-{r['arr_apt']}"
        stop = U['nonstop'] if r['stops'] else U['connecting']
        # 幣別符號寬度各異（NT$ 佔 3 格、¥ 佔 1 格），先跟數字組成字串再整欄右對齊，
        # 否則換幣別時價格欄會參差。
        out.append(f"{P(sym + format(r['price'], ','), 11, '>')}  {P(r['airline'], 14)} "
                   f"{P(r['dep'] + '-' + r['arr'], 19)} {P(route, 9)} {P(stop, 6)} {r['duration']}")
    tail = f"\n{U['total_n'].format(n=len(rows))} | {U['lowest']} {sym}{rows[0]['price']:,}"
    if len(rows) > limit:
        # 「共 N 筆」與實際印出的筆數不一致，是這支腳本最容易誤導人的地方：結果依
        # 價格排序，而直飛與全服務航空通常較貴，會被系統性地排到截斷線之外。
        tail += U['truncated'].format(shown=limit, n_more=len(rows) - limit)
    out.append(tail)
    return warn + '\n'.join(out)


if __name__ == '__main__':
    lang = os.environ.get('GFH_LANG')
    if '--lang' in sys.argv:
        lang = sys.argv[sys.argv.index('--lang') + 1]
    top = int(os.environ.get('GFH_TOP') or 12)
    if '--top' in sys.argv:
        top = int(sys.argv[sys.argv.index('--top') + 1])
    sym = locales.symbol_for(os.environ.get('GFH_CURR'))
    page = sys.stdin.read()
    dropped = {}
    print(render(parse(page, lang, dropped), limit=top, lang=lang, symbol=sym,
                 title=page_title(page), dropped=dropped))
