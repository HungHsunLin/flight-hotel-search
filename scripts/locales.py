"""語言包 — 把 Google 各語系的自然語言 aria-label 轉回結構化資料。

## 為什麼需要這一層，而不是「把 hl 換掉就好」

Google 把搜尋結果寫進 aria-label 的**自然語言句子**裡，而各語系的語序完全不同：

  zh-TW  來回總價 <價格> 新台幣起。 搭乘<航空公司>的直達航班。 … 於<機場>出發，…
  en     From <price> US dollars round trip total. Nonstop flight with <airline>. Leaves <airport> …
  ja     往復の合計金額 <価格> 円～。 <航空会社> が運航する直行便。 … <空港>発、…

飯店更極端，價格與名稱**前後順序是反的**：

  zh-TW  <飯店名>，價格 $<價格> 起          ← 名稱在前
  en     Prices starting from $<price>, <hotel>   ← 價格在前
  ja     <ホテル名>、NT$<価格>～                  ← 名稱在前

所以不可能用一組通用 regex 覆蓋。解法是每個語系一組具名群組（name/price/dep/arr…），
regex 內部順序隨語系而變，呼叫端一律用群組名取值。

## 這些 regex 是實測來的，不是推的

每一條都是實際抓該語系頁面、比對真實輸出寫出來的。照文法推的 regex 會**安靜地回空
清單**——跟「地名打錯」「被限流」長得一模一樣（見 SKILL.md 的陷阱章節）。

實測過程中發現三個只有換語系才會浮現的坑，都已反映在下面的設定裡：

  1. **英文 label 比中日文長一倍以上**。實測直飛航班：en 233~277 字元、zh-TW 僅
     108~131、ja 103~123。原本 400 字元的擷取上限對實測到的直飛航班仍然夠用
     （沒有一筆超過），但這個餘裕是巧合而非設計——轉機航段會列出更多航段描述，
     長度未經驗證。故 label_len 改為逐語系設定，英文放寬到 700 留出餘裕。
  2. **英文價格拼出貨幣全名**（`From <price> US dollars`），沒有 $ 符號，用符號比對會 0 筆。
  3. **英文時間用 U+202F 窄空格**（`12:10 PM`）而非普通空格，寫死 ' ' 會對不到。

## 新增一個語系

複製一組 LOCALES 條目，**實際抓一次該語系的頁面**把 regex 對到真實輸出，然後確認
解析筆數 > 0。不要跳過實測：Google 對解不出來的情況不會報錯，只會回空。
"""
import unicodedata

# 機場全名 → IATA 代碼。用城市名查詢（「臺北市」「Tokyo」）會把多個機場混在一起回，
# 這張表讓輸出能標出實際是哪個機場——桃園還是松山、成田還是羽田，直接影響進出市區
# 的時間與交通費，不能省略。
#
# 刻意做成「一個代碼對多語別名」而不是每語系一張表：新增語系時只要往現有條目加別名，
# 不必整張表複製一份。
AIRPORTS = {
    'TPE': ['臺灣桃園國際機場', '桃園國際機場', 'Taiwan Taoyuan International Airport', '台湾桃園国際空港'],
    'TSA': ['臺北松山機場', '松山機場', 'Taipei Songshan Airport', '台北松山空港'],
    'NRT': ['成田國際機場', 'Narita International Airport', '成田国際空港'],
    'HND': ['東京國際機場(羽田機場)', '東京國際機場（羽田機場）', '羽田機場',
            'Haneda Airport', 'Tokyo Haneda International Airport', '東京国際空港', '羽田空港'],
    'KIX': ['關西國際機場', 'Kansai International Airport', '関西国際空港'],
    'ITM': ['大阪國際機場(伊丹機場)', '伊丹機場', 'Osaka International Airport', 'Itami Airport', '大阪国際空港', '伊丹空港'],
    'NGO': ['中部國際機場', 'Chubu Centrair International Airport', '中部国際空港'],
    'CTS': ['新千歲機場', 'New Chitose Airport', '新千歳空港'],
    'FUK': ['福岡機場', 'Fukuoka Airport', '福岡空港'],
    'OKA': ['那霸機場', 'Naha Airport', '那覇空港'],
    'KMQ': ['小松機場', 'Komatsu Airport', '小松空港'],
    'ICN': ['仁川國際機場', 'Incheon International Airport', '仁川国際空港'],
    'HKG': ['香港國際機場', 'Hong Kong International Airport', '香港国際空港'],
    'SIN': ['樟宜機場', 'Singapore Changi Airport', 'シンガポール・チャンギ国際空港'],
}


def airport_code(name):
    """機場全名 → IATA 代碼；查不到就回原名前幾個字（至少讓使用者看得出是哪裡）。"""
    name = (name or '').strip()
    if not name:
        return '?'
    for code, aliases in AIRPORTS.items():
        if name in aliases:
            return code
    for code, aliases in AIRPORTS.items():
        if any(a in name for a in aliases):
            return code
    return name[:4]


LOCALES = {
    'zh-TW': {
        'region': 'tw',
        'currency': 'TWD',
        'symbol': 'NT$',
        # 飯店查詢字串。Google 靠這個判斷你要找住宿，語系不同寫法也不同。
        'hotel_query': '{place}飯店',
        'label_len': (40, 500),
        'flight': {
            'marker': '出發',
            # 幣別不是固定的（hl=zh-TW 也可能配 curr=JPY，那就會變「日圓」），
            # 所以先抓語序固定的「總價 N」，抓不到才退回逐一列舉幣別名。
            'price': [r'總價\s*([\d,]+)',
                      r'([\d,]+)\s*(?:新台幣|日圓|美元|歐元|韓元|港幣|人民幣|英鎊|澳幣)'],
            'airline': r'搭乘(.+?)的',
            'route': r'(?P<dep>\S*?\d+:\d+) 於(?P<dep_apt>.+?)出發.*?'
                     r'(?P<arr>\S*?\d+:\d+) 抵達(?P<arr_apt>.+?)。',
            'duration': r'總交通時間：(.+?)(?:\s{2,}|$)',
            'nonstop': '直達',
        },
        'hotel': {
            'price': r'^(?P<name>.+?)，價格 \D{0,4}(?P<price>[\d,]+) 起(?P<rest>.*)$',
            'rating': r'^在「(?P<name>.+?)」的 (?P<reviews>[\d,]+) 則評論中獲得 (?P<stars>[\d.]+) 顆星',
            'deal': r'比市價便宜 (\d+%)',
        # 總價不在 aria-label 裡，而在一般文字節點，且該節點不帶飯店名。
        # 用 > < 夾住節點文字比對，不依賴 class 名（CQYfx 這類 class Google 隨時會換）。
        'total': r'>總價為\s*\D{0,4}(?P<total>[\d,]+)\s*<',
        'nights': r'>\s*(?P<nights>\d+) 晚\s*[（(]含稅',
        },
        # gnolcc.py 用。SKILL.md 實測：航空公司篩選必須用**該語系介面的寫法**，
        # 送錯語言的名稱 Google 回 0 筆而不是報錯。
        'full_service': ['中華航空', '長榮航空', '星宇航空', '日本航空', '全日空航空',
                         '國泰航空', '韓亞航空', '大韓航空', '泰國航空', '新加坡航空'],
        'ui': {
            'no_data_flight': '(無資料 — 檢查機場代碼或日期)',
            'no_data_hotel': '(無資料 — 檢查地名或日期)',
            'price': '價格', 'airline': '航空', 'outbound': '去程時段', 'route': '起降',
            'stops': '停', 'duration': '飛行時間', 'nonstop': '直達', 'connecting': '轉機',
            'total_n': '共 {n} 筆', 'lowest': '最低',
            'nightly': '每晚房價', 'total': '總價', 'rating': '評分', 'hotel': '飯店',
            'note': '備註',
            'total_hotels': '共 {n} 間', 'median': '每晚房價中位數', 'range': '每晚房價區間',
            'total_median': '{n} 晚總價中位數',
            'total_mismatch': '⚠️ 有 {n} 筆總價與「每晚 × 晚數」對不上——版面可能改過、'
                              '總價配對到錯誤的飯店。請以每晚房價為準並回報。',
            'hotel_footnote': '（每晚房價與總價都已含稅金與相關費用。總價取自 Google 頁面本身，'
                              '實測等於每晚 × 晚數，差異僅來自四捨五入——連泊折扣若存在，'
                              '早已算進每晚均價裡了）',
            'past_date': '錯誤：{what} {date} 已經是過去的日期（今天是 {today}）。',
            'past_hint': '使用者說的月份如果沒講年份、且那個月今年已經過了，該用明年，不是今年。',
            'depart_date': '出發日', 'start_date': '起始日',
            'oneway': '{d} 單程',
            'per_airline': '逐家查詢 {n} 家全服務航空',
            'filter_note': '（航空公司篩選同時套用到去程與回程，所以不會出現「去程正常、回程廉航」的混搭）',
            'no_route': '(無資料 — 檢查地名與日期，或這條航線沒有全服務航空直飛)',
            'no_flights_for': '無航班/無資料：',
            'stay_flight': '停留 {n} 晚', 'stay_hotel': '住 {n} 晚',
            'scanning': '掃描 {title}：{start} ~ {end}（{n} 個日期，並行 {w}）',
            'scan_hotel_note': '（飯店依「當日房價中位數」排序 — 最低價常是青旅，不代表整體行情）',
            'scan_empty': '(全部無資料 — 檢查參數，或 Google 開始限流了)',
            'rank': '排名', 'median_col': '中位數', 'depart_col': '出發', 'checkin_col': '入住',
            'return_col': '回/退', 'content_col': '內容',
            'dates_with_data': '{ok}/{all} 個日期有資料', 'highest': '最高', 'spread': '價差',
            'throttle_warn': '注意：{n} 個日期沒回資料，可能是限流而非真的無航班/無房',
        },
    },

    'en': {
        'region': 'us',
        'currency': 'USD',
        'symbol': '$',
        'hotel_query': '{place} hotels',
        # 英文句子比中日文長得多（實測直飛完整 label 233~277 字元，中文同內容約
        # 108~131）。700 是留給多段轉機的餘裕：轉機會列出每個航段，長度未實測，
        # 而上限設得太小的後果是靜默丟掉抵達時間與總時長，不會有任何錯誤訊息。
        'label_len': (40, 700),
        'flight': {
            'marker': 'Select flight',
            # 英文把貨幣拼成全名（'From <price> US dollars'），沒有 $ 符號。
            # 幣別名會隨 curr 改變，所以錨在固定的 'From N' 語序上，別碰貨幣名。
            'price': [r'From ([\d,]+)\s+[^.]*?total', r'From ([\d,]+)\b'],
            'airline': r'flight with (.+?)\.',
            # 時間是 '12:10 PM'——U+202F 窄不斷行空格，不是普通空格。
            # \s 在 Python3 的 Unicode 模式下涵蓋它，但明寫出來免得日後有人「優化」成 ' '。
            'route': r'Leaves (?P<dep_apt>.+?) at (?P<dep>\d{1,2}:\d{2}[\s ]*[AP]M)'
                     r'.*?arrives at (?P<arr_apt>.+?) at (?P<arr>\d{1,2}:\d{2}[\s ]*[AP]M)',
            'duration': r'Total duration (.+?)\.',
            'nonstop': 'Nonstop',
        },
        'hotel': {
            # 折扣尾綴有兩種：小折扣是 DEAL、大折扣是 GREAT DEAL（實抓確認，37/50/29%
            # 那幾筆都是 GREAT DEAL）。漏掉 GREAT 的話它會被當成名稱的一部分，
            # 產出「HOTEL AMANEK Kumamoto GREAT」這種看起來只是有點怪的名字。
            # 名稱在最後，而 DEAL 尾綴只隔一個空格——用非貪婪加可選尾巴會讓 name 把
            # 'X DEAL 23% less than usual' 整段吃進去。lookahead 才切得乾淨。
            'price': r'^Prices starting from \D{0,4}(?P<price>[\d,]+), (?P<name>.+?)(?=\s+(?:GREAT\s+)?DEAL\s|$)',
            'rating': r'^(?P<stars>[\d.]+) out of 5 stars from (?P<reviews>[\d,]+) reviews, (?P<name>.+)$',
            'deal': r'DEAL (\d+%) less than usual',
        'total': r'>\s*\D{0,4}(?P<total>[\d,]+)\s+total\s*<',
        'nights': r'>\s*(?P<nights>\d+) nights? with taxes',
        },
        'full_service': ['China Airlines', 'EVA Air', 'STARLUX Airlines', 'Japan Airlines',
                         'All Nippon Airways', 'Cathay Pacific', 'Asiana Airlines',
                         'Korean Air', 'Thai Airways', 'Singapore Airlines'],
        'ui': {
            'no_data_flight': '(no data - check airport codes or dates)',
            'no_data_hotel': '(no data - check place name or dates)',
            'price': 'Price', 'airline': 'Airline', 'outbound': 'Outbound', 'route': 'Route',
            'stops': 'Stop', 'duration': 'Duration', 'nonstop': 'Direct', 'connecting': 'Connect',
            'total_n': '{n} results', 'lowest': 'lowest',
            'nightly': 'Per night', 'total': 'Total', 'rating': 'Rating', 'hotel': 'Hotel',
            'note': 'Note',
            'total_hotels': '{n} hotels', 'median': 'median nightly', 'range': 'nightly range',
            'total_median': 'median {n}-night total',
            'total_mismatch': 'WARNING: {n} totals disagree with nightly x nights — the page '
                              'layout may have changed and totals may be paired with the wrong '
                              'hotel. Trust the nightly rate and report this.',
            'hotel_footnote': '(Both the nightly rate and the total include taxes and fees. The '
                              'total is read from the page itself and equals nightly x nights, '
                              'differing only by rounding — any multi-night discount is already '
                              'baked into the nightly average.)',
            'past_date': 'Error: {what} {date} is in the past (today is {today}).',
            'past_hint': 'If a month was given with no year and it has already passed, use next year.',
            'depart_date': 'departure date', 'start_date': 'start date',
            'oneway': '{d} one-way',
            'per_airline': 'querying {n} full-service carriers one by one',
            'filter_note': '(The airline filter applies to BOTH legs, so you will not get a '
                           'full-service outbound paired with a budget return.)',
            'no_route': '(no data - check place names and dates, or no full-service carrier flies this route)',
            'no_flights_for': 'no flights/no data: ',
            'stay_flight': '{n}-night stay', 'stay_hotel': '{n} nights',
            'scanning': 'Scanning {title}: {start} ~ {end} ({n} dates, {w} parallel)',
            'scan_hotel_note': '(Hotels ranked by MEDIAN nightly rate - the cheapest listing is '
                               'often a hostel and does not represent the market.)',
            'scan_empty': '(no data at all - check the arguments, or Google started throttling)',
            'rank': '#', 'median_col': 'Median', 'depart_col': 'Depart', 'checkin_col': 'Check-in',
            'return_col': 'Ret/Out', 'content_col': 'Detail',
            'dates_with_data': '{ok}/{all} dates returned data', 'highest': 'highest', 'spread': 'spread',
            'throttle_warn': 'Note: {n} dates returned nothing - likely throttling, not genuinely sold out',
        },
    },

    'ja': {
        'region': 'jp',
        'currency': 'JPY',
        'symbol': '¥',
        'hotel_query': '{place} ホテル',
        'label_len': (30, 500),
        'flight': {
            'marker': 'フライトを選択',
            'price': [r'合計金額\s*([\d,]+)', r'([\d,]+)\s*円'],
            # 航空公司前面是句號後的空白，用句號錨定避免把前一句一起吃進來。
            'airline': r'。\s*(.+?)\s*が運航する',
            # 日文把機場放在時間**後面**、用「発／着」結尾——跟中英文的前置語序相反。
            'route': r'(?P<dep>\d{1,2}:\d{2})\s*(?P<dep_apt>.+?)発、.*?'
                     r'(?P<arr>\d{1,2}:\d{2})\s*(?P<arr_apt>.+?)着',
            'duration': r'合計時間\s*(.+?)。',
            'nonstop': '直行便',
        },
        'hotel': {
            'price': r'^(?P<name>.+?)、\D{0,4}(?P<price>[\d,]+)～(?P<rest>.*)$',
            'rating': r'^(?P<reviews>[\d,]+) 件の評価で (?P<stars>[\d.]+) つ星（最高は 5 つ星）'
                      r'（(?P<name>.+?)）$',
            'deal': r'通常より (\d+%) お得',
        # 全形 ￥ (U+FFE5)，不是 ¥ (U+00A5)——實抓頁面確認過，照文法推會寫錯。
        'total': r'>\s*合計\s*\D{0,4}(?P<total>[\d,]+)\s*<',
        'nights': r'>\s*(?P<nights>\d+) 泊[（(]税',
        },
        'full_service': ['チャイナ エアライン', 'エバー航空', 'スターラックス航空', '日本航空',
                         '全日空', 'キャセイパシフィック航空', 'アシアナ航空', '大韓航空',
                         'タイ国際航空', 'シンガポール航空'],
        'ui': {
            'no_data_flight': '(データなし — 空港コードまたは日付を確認)',
            'no_data_hotel': '(データなし — 地名または日付を確認)',
            'price': '料金', 'airline': '航空会社', 'outbound': '往路', 'route': '発着',
            'stops': '経由', 'duration': '所要時間', 'nonstop': '直行', 'connecting': '経由',
            'total_n': '{n} 件', 'lowest': '最安',
            'nightly': '1泊料金', 'total': '総額', 'rating': '評価', 'hotel': 'ホテル',
            'note': '備考',
            'total_hotels': '{n} 軒', 'median': '1泊料金の中央値', 'range': '1泊料金の範囲',
            'total_median': '{n}泊総額の中央値',
            'total_mismatch': '⚠️ {n} 件の総額が「1泊 × 泊数」と一致しません。ページ構造が'
                              '変わり、総額が別のホテルに紐づいた可能性があります。'
                              '1泊料金を優先してください。',
            'hotel_footnote': '（1泊料金・総額とも税・サービス料込みです。総額はページから直接'
                              '取得した値で、1泊 × 泊数と一致します（差は端数処理のみ）。'
                              '連泊割引があれば1泊平均に反映済みです）',
            'past_date': 'エラー：{what} {date} は過去の日付です（今日は {today}）。',
            'past_hint': '年を伴わない月の指定で、その月が既に過ぎている場合は翌年を使ってください。',
            'depart_date': '出発日', 'start_date': '開始日',
            'oneway': '{d} 片道',
            'per_airline': 'フルサービス航空 {n} 社を個別に検索',
            'filter_note': '（航空会社フィルタは往復**両方**に適用されるため、'
                           '往路のみ大手・復路LCCという混在は起きません）',
            'no_route': '(データなし — 地名と日付を確認、またはこの路線にフルサービス便がありません)',
            'no_flights_for': '便なし/データなし：',
            'stay_flight': '{n} 泊', 'stay_hotel': '{n} 泊',
            'scanning': 'スキャン {title}：{start} ~ {end}（{n} 日分、並列 {w}）',
            'scan_hotel_note': '（ホテルは「当日料金の中央値」順 — 最安値はゲストハウスが多く相場を表しません）',
            'scan_empty': '(全てデータなし — 引数を確認、または制限がかかっています)',
            'rank': '順位', 'median_col': '中央値', 'depart_col': '出発', 'checkin_col': 'チェックイン',
            'return_col': '復路/退室', 'content_col': '内容',
            'dates_with_data': '{ok}/{all} 日分のデータ取得', 'highest': '最高', 'spread': '価格差',
            'throttle_warn': '注意：{n} 日分が空です。実際に満室/無便ではなく制限の可能性があります',
        },
    },
}

# 幣別代碼 → 顯示符號。查不到就直接印代碼（"CHF 120"），總比印錯符號好。
CURRENCY_SYMBOLS = {
    'TWD': 'NT$', 'USD': '$', 'JPY': '¥', 'EUR': '€', 'KRW': '₩', 'HKD': 'HK$',
    'CNY': 'CN¥', 'GBP': '£', 'AUD': 'A$', 'SGD': 'S$', 'THB': '฿', 'MYR': 'RM',
    'PHP': '₱', 'VND': '₫', 'IDR': 'Rp', 'INR': '₹', 'CAD': 'C$', 'CHF': 'CHF ',
}


def symbol_for(curr):
    """幣別代碼 → 符號。給 render 用，讓輸出的錢符號跟實際查詢幣別一致。"""
    if not curr:
        return None
    return CURRENCY_SYMBOLS.get(curr.upper(), curr.upper() + ' ')


DEFAULT = 'zh-TW'


def get(lang=None):
    """取語言包。未知語系回退到預設，而不是拋例外——查詢還是能跑，只是介面語言不同。"""
    return LOCALES.get(lang or DEFAULT, LOCALES[DEFAULT])


def resolve(lang=None):
    """回 (lang_code, locale_dict)。呼叫端要拿實際生效的語系去組 URL 的 hl 參數。"""
    code = lang if lang in LOCALES else DEFAULT
    return code, LOCALES[code]


# 預設 User-Agent。Google 對非瀏覽器 UA 會回不同結構的頁面，解析直接拿到空結果，
# 所以預設仍是一般瀏覽器字串。要換成自訂識別就設 GFH_UA（見 README 的說明）。
DEFAULT_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


def dwidth(s):
    """字串在等寬終端的顯示寬度。CJK 全形字元佔 2 格——用 len() 對齊，中日文欄位
    會整排跑掉（英文欄位看起來正常，所以這個 bug 只在換語系後才浮現）。"""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def dtrunc(s, width):
    """依顯示寬度截斷，不切在全形字元中間。"""
    out, w = '', 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in 'WF' else 1
        if w + cw > width:
            break
        out += c
        w += cw
    return out


def dpad(s, width, align='<'):
    """依顯示寬度補空白（不是字元數）。align='>' 為右對齊。"""
    s = dtrunc(str(s), width)
    gap = max(0, width - dwidth(s))
    return (s + ' ' * gap) if align == '<' else (' ' * gap + s)


def from_env():
    """從環境變數取整組設定，回 (lang, locale, currency, region, ua)。

    未設定時一律回退到 zh-TW / TWD / tw，與加入多語支援前的行為一致。
    """
    import os
    code, L = resolve(os.environ.get('GFH_LANG'))
    return (code, L,
            os.environ.get('GFH_CURR') or L['currency'],
            os.environ.get('GFH_REGION') or L['region'],
            os.environ.get('GFH_UA') or DEFAULT_UA)


if __name__ == '__main__':
    # 給 shell 取值用，避免語言包資訊在 shell 裡再抄一份而走鐘。
    #   python3 locales.py hotel_query en 金澤   -> "金澤 hotels"
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'hotel_query':
        _, L = resolve(sys.argv[2])
        print(L['hotel_query'].format(place=' '.join(sys.argv[3:])))
    elif len(sys.argv) >= 3 and sys.argv[1] == 'field':
        _, L = resolve(sys.argv[2])
        print(L.get(sys.argv[3], ''))
    else:
        print(' '.join(LOCALES))
