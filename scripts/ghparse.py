"""解析 Google Hotels 搜尋結果頁。可當 CLI（吃 stdin）或 import 用。

語系由 locales.py 的語言包決定；不帶語系時走 zh-TW，與加入多語支援前的行為一致。

價格與評分分別散在不同的 aria-label 裡，靠**飯店名**配對。三個語系的評分 label 都
帶名稱，只是位置不同（en 在句尾、ja 在全形括號內、zh 在直角引號內），語言包已吸收
這個差異，這裡統一用具名群組 name 取值。
"""
import sys, os, re, html, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locales


def parse(page, lang=None):
    """回傳 [{price, name, stars, reviews, deal}]，依價格排序。"""
    _, L = locales.resolve(lang)
    H = L['hotel']
    lo, hi = L['label_len']
    labs = [html.unescape(x) for x in
            re.findall(r'aria-label="([^"]{10,%d}?)"' % hi, page)]

    price, rate = {}, {}
    for s in labs:
        m = re.match(H['price'], s)
        if m:
            g = m.groupdict()
            # deal 從整個 label 搜，不依賴 rest 群組——各語系折扣字樣的位置不同
            # （en 在名稱後、ja 在價格後、zh 在價格後），統一搜尋比逐語系接線可靠。
            d = re.search(H['deal'], s)
            price.setdefault(g['name'].strip(),
                             (g['price'], d.group(1) if d else ''))
        r = re.match(H['rating'], s)
        if r:
            g = r.groupdict()
            rate.setdefault(g['name'].strip(), (g['stars'], g['reviews']))

    rows = []
    for n, (p, d) in price.items():
        st, nr = rate.get(n, ('', ''))
        rows.append({'price': int(p.replace(',', '')), 'name': n,
                     'stars': st, 'reviews': nr, 'deal': d})
    rows.sort(key=lambda r: r['price'])
    return rows


def render(rows, lang=None, symbol=None):
    _, L = locales.resolve(lang)
    U = L['ui']
    sym = symbol or L['symbol']
    if not rows:
        return U['no_data_hotel']

    P = locales.dpad
    out = [f"{P(U['nightly'], 11, '>')}  {P(U['rating'], 13)} {P(U['hotel'], 36)} {U['note']}",
           '-' * 78]
    for r in rows:
        stars = f"{r['stars']}* ({r['reviews']})" if r['stars'] else ''
        out.append(f"{P(sym + format(r['price'], ','), 11, '>')}  {P(stars, 13)} "
                   f"{P(r['name'], 36)} {r['deal']}")
    v = [r['price'] for r in rows]
    out.append(f"\n{U['total_hotels'].format(n=len(rows))} | "
               f"{U['median']} {sym}{int(statistics.median(v)):,} | "
               f"{U['range']} {sym}{min(v):,}-{max(v):,}"
               f"\n{U['hotel_footnote']}")
    return '\n'.join(out)


if __name__ == '__main__':
    lang = os.environ.get('GFH_LANG')
    if '--lang' in sys.argv:
        lang = sys.argv[sys.argv.index('--lang') + 1]
    sym = locales.symbol_for(os.environ.get('GFH_CURR'))
    print(render(parse(sys.stdin.read(), lang), lang=lang, symbol=sym))
