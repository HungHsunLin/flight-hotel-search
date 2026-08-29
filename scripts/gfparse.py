"""解析 Google Flights 搜尋結果頁。可當 CLI（吃 stdin）或 import 用。

語系由 locales.py 提供的語言包決定。不帶語系時走 zh-TW，與加入多語支援前的行為一致。
CLI 用 --lang 指定，或設環境變數 GFH_LANG。
"""
import sys, os, re, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locales


def parse(page, lang=None):
    """回傳 [{price, airline, dep, arr, dep_apt, arr_apt, stops, duration}]，依價格排序。"""
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


def render(rows, limit=12, lang=None, symbol=None):
    _, L = locales.resolve(lang)
    U = L['ui']
    sym = symbol or L['symbol']
    if not rows:
        return U['no_data_flight']

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
    out.append(f"\n{U['total_n'].format(n=len(rows))} | {U['lowest']} {sym}{rows[0]['price']:,}")
    return '\n'.join(out)


if __name__ == '__main__':
    lang = os.environ.get('GFH_LANG')
    if '--lang' in sys.argv:
        lang = sys.argv[sys.argv.index('--lang') + 1]
    sym = locales.symbol_for(os.environ.get('GFH_CURR'))
    print(render(parse(sys.stdin.read(), lang), lang=lang, symbol=sym))
