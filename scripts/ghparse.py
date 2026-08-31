"""解析 Google Hotels 搜尋結果頁。可當 CLI（吃 stdin）或 import 用。

語系由 locales.py 的語言包決定；不帶語系時走 zh-TW，與加入多語支援前的行為一致。

價格與評分分別散在不同的 aria-label 裡，靠**飯店名**配對。三個語系的評分 label 都
帶名稱，只是位置不同（en 在句尾、ja 在全形括號內、zh 在直角引號內），語言包已吸收
這個差異，這裡統一用具名群組 name 取值。

**總價是唯一一個不能靠名稱配對的欄位**——它不在 aria-label 裡，而在一般文字節點
（zh「總價為 $12,067」、en「$381 total」、ja「合計 ￥68,216」），節點本身不帶飯店名。
版面順序固定是「價格 label → 總價 → 評分 label」，所以改用位置錨定：每筆總價屬於它
前面最近的那個價格 label。刻意不比對 class 名（實際頁面是 CQYfx UDzrdc 這類混淆過的
名稱，Google 隨時會換）。

位置錨定一旦失準，產出的會是「數字都對、但配到錯的飯店」——完全看不出異常。所以
render() 會拿每筆總價對「每晚 × 晚數」核帳，對不上就在輸出末尾示警。
"""
import sys, os, re, html, statistics, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locales


def parse(page, lang=None):
    """回傳 [{price, total, nights, name, stars, reviews, deal}]，依每晚房價排序。

    total 為 0 代表該筆沒抓到總價（欄位缺漏時留白，不用每晚 × 晚數頂替——
    那會讓「頁面沒給」和「頁面給了」變得無法區分）。
    """
    _, L = locales.resolve(lang)
    H = L['hotel']
    lo, hi = L['label_len']
    labs = [(m.start(), html.unescape(m.group(1))) for m in
            re.finditer(r'aria-label="([^"]{10,%d}?)"' % hi, page)]

    price, rate, price_at = {}, {}, []
    for pos, s in labs:
        m = re.match(H['price'], s)
        if m:
            g = m.groupdict()
            # deal 從整個 label 搜，不依賴 rest 群組——各語系折扣字樣的位置不同
            # （en 在名稱後、ja 在價格後、zh 在價格後），統一搜尋比逐語系接線可靠。
            d = re.search(H['deal'], s)
            name = g['name'].strip()
            price.setdefault(name, (g['price'], d.group(1) if d else ''))
            price_at.append((pos, name))
        r = re.match(H['rating'], s)
        if r:
            g = r.groupdict()
            rate.setdefault(g['name'].strip(), (g['stars'], g['reviews']))

    # 晚數整頁共用（每張卡片印的都是同一個數字），抓一次即可。
    nm = re.search(H['nights'], page)
    nights = int(nm.group('nights')) if nm else 0

    # finditer 依位置遞增回傳，所以 price_at 本身已排序，可直接二分搜尋。
    # 同一張卡片的總價在頁面上會重複出現兩次，setdefault 取第一次。
    starts = [p for p, _ in price_at]
    total = {}
    for m in re.finditer(H['total'], page):
        i = bisect.bisect_right(starts, m.start()) - 1
        if i >= 0:
            total.setdefault(price_at[i][1],
                             int(m.group('total').replace(',', '')))

    rows = []
    for n, (p, d) in price.items():
        st, nr = rate.get(n, ('', ''))
        rows.append({'price': int(p.replace(',', '')), 'total': total.get(n, 0),
                     'nights': nights, 'name': n,
                     'stars': st, 'reviews': nr, 'deal': d})
    rows.sort(key=lambda r: r['price'])
    return rows


def mismatched(rows):
    """回傳總價與「每晚 × 晚數」對不上的筆數。

    容許值取 max(3, 晚數)：每晚價本身是四捨五入過的，乘開後誤差會隨晚數線性放大。
    實測 4 組查詢共 72 間（2/3/5/7 晚）最大誤差 3 元，全部落在容許範圍內。
    """
    n = rows[0]['nights'] if rows else 0
    if not n:
        return 0
    return sum(1 for r in rows
               if r['total'] and abs(r['total'] - r['price'] * n) > max(3, n))


def render(rows, lang=None, symbol=None):
    _, L = locales.resolve(lang)
    U = L['ui']
    sym = symbol or L['symbol']
    if not rows:
        return U['no_data_hotel']

    P = locales.dpad
    money = lambda v: sym + format(v, ',')
    has_total = any(r['total'] for r in rows)
    nights = rows[0]['nights']

    head = P(U['nightly'], 11, '>') + '  '
    if has_total:
        head += P(U['total'], 11, '>') + '  '
    head += f"{P(U['rating'], 13)} {P(U['hotel'], 36)} {U['note']}"
    out = [head, '-' * (91 if has_total else 78)]

    for r in rows:
        stars = f"{r['stars']}* ({r['reviews']})" if r['stars'] else ''
        line = P(money(r['price']), 11, '>') + '  '
        if has_total:
            line += P(money(r['total']) if r['total'] else '', 11, '>') + '  '
        line += f"{P(stars, 13)} {P(r['name'], 36)} {r['deal']}"
        out.append(line)

    v = [r['price'] for r in rows]
    summary = (f"\n{U['total_hotels'].format(n=len(rows))} | "
               f"{U['median']} {sym}{int(statistics.median(v)):,} | "
               f"{U['range']} {sym}{min(v):,}-{max(v):,}")
    if has_total:
        t = [r['total'] for r in rows if r['total']]
        summary += (f"\n{U['total_median'].format(n=nights)} "
                    f"{sym}{int(statistics.median(t)):,} "
                    f"({sym}{min(t):,}-{sym}{max(t):,})")
    out.append(summary + f"\n{U['hotel_footnote']}")

    bad = mismatched(rows)
    if bad:
        out.append(U['total_mismatch'].format(n=bad))
    return '\n'.join(out)


if __name__ == '__main__':
    lang = os.environ.get('GFH_LANG')
    if '--lang' in sys.argv:
        lang = sys.argv[sys.argv.index('--lang') + 1]
    sym = locales.symbol_for(os.environ.get('GFH_CURR'))
    print(render(parse(sys.stdin.read(), lang), lang=lang, symbol=sym))
