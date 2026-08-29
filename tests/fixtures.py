"""合成測試資料 — 模仿 Google 頁面的 aria-label 格式，內容全屬虛構。

**這裡沒有任何一個位元組來自 Google。** 航空公司、飯店、價格全是編造的
（Example Air / 範例航空 / サンプル航空、9999 元…）；只有機場名稱用真實地名，
因為那正是 locales.AIRPORTS 對照表要驗證的目標，而地名是事實、不屬任何人的著作。

這樣做的兩個理由：

  1. 測試不需要網路，也不隨 Google 改版而變紅——測的是「我們的 regex 有沒有照
     設計運作」，不是「Google 今天回什麼」。
  2. 專案裡不留任何來源網站的內容。抓一份真實 HTML 存進 repo 當 fixture 是最省事
     的做法，但那等於把別人的頁面複製進版本庫。

格式若與 Google 實際輸出脫節，測試會全綠而線上全壞——所以**改動 locales.py 的
regex 時，必須同時用真實頁面對照一次**，不能只靠這裡的綠燈。
"""

# --- Flights ---------------------------------------------------------------
# 英文那筆刻意保留兩個真實世界的特性：
#   * 句子比中日文長得多——實測直飛航班 en 為 233~277 字元、zh-TW 僅 108~131，
#     所以擷取長度上限必須逐語系設定，不能照中文的長度套用到所有語系。
#   * 時間使用 U+202F 窄不斷行空格，不是普通空格（寫死 ' ' 會對不到）。
#
# 第三筆 'en' 是**合成的超長 label**（>400 字元），用來驗證 label_len 上限確實
# 生效。實測到的真實直飛 label 最長 277 字元，尚未觸及上限；轉機航段是否更長
# 未經驗證（測試時該航線被限流）。這筆的作用是守住「上限設得夠寬」這個機制，
# 而不是宣稱真實資料長這樣——格式是照直飛句型外推的。
FLIGHT_LABELS = {
    'zh-TW': [
        '來回總價 9,999 新台幣起。 搭乘範例航空的直達航班。 星期四, 10月 1 中午12:00 '
        '於臺灣桃園國際機場出發，星期四, 10月 1 下午3:30 抵達成田國際機場。 '
        '總交通時間：3 小時 30 分鐘   選擇航班',
        '來回總價 12,345 新台幣起。 搭乘測試航空的轉機航班。 星期五, 10月 2 上午8:00 '
        '於臺北松山機場出發，星期五, 10月 2 中午12:45 抵達東京國際機場(羽田機場)。 '
        '總交通時間：4 小時 45 分鐘   選擇航班',
    ],
    'en': [
        'From 999 US dollars round trip total. Nonstop flight with Example Air. '
        'Leaves Taiwan Taoyuan International Airport at 12:00 PM on Thursday, October 1 '
        'and arrives at Narita International Airport at 3:30 PM on Thursday, October 1. '
        'Total duration 3 hr 30 min.   Select flight',
        'From 1,234 US dollars round trip total. 1 stop flight with Testing Airways. '
        'Leaves Taipei Songshan Airport at 8:00 AM on Friday, October 2 '
        'and arrives at Haneda Airport at 12:45 PM on Friday, October 2. '
        'Total duration 4 hr 45 min.   Select flight',
        # 合成的超長樣本，見檔頭說明。長度刻意超過 400 字元。
        'From 2,345 US dollars round trip total. 2 stop flight with Testing Airways. '
        'Leaves Taiwan Taoyuan International Airport at 6:00 AM on Saturday, October 3 '
        'and arrives at Kansai International Airport at 9:30 AM on Saturday, October 3, '
        'then departs Kansai International Airport at 11:00 AM on Saturday, October 3 '
        'and arrives at Chubu Centrair International Airport at 1:15 PM on Saturday, '
        'October 3, then continues to Narita International Airport arriving at 5:45 PM '
        'on Saturday, October 3. Total duration 11 hr 45 min.   Select flight',
    ],
    'ja': [
        '往復の合計金額 99,999 円～。 サンプル航空 が運航する直行便。 木曜日, 10月 1 '
        '12:00 台湾桃園国際空港発、木曜日, 10月 1 15:30 成田国際空港着。 '
        '合計時間 3 時間 30 分。   フライトを選択',
        '往復の合計金額 123,456 円～。 テスト航空 が運航する1回経由。 金曜日, 10月 2 '
        '8:00 台北松山空港発、金曜日, 10月 2 12:45 羽田空港着。 '
        '合計時間 4 時間 45 分。   フライトを選択',
    ],
}

# --- Hotels ----------------------------------------------------------------
# 每個語系都放一筆帶折扣、一筆不帶。折扣那筆是回歸重點：英文的 DEAL 尾綴只隔一個
# 空格，早期的非貪婪比對會把「… DEAL 25% less than usual」整段吃進飯店名。
HOTEL_LABELS = {
    'zh-TW': [
        '範例飯店，價格 $1,234 起 比市價便宜 25%',
        '測試旅館，價格 $2,468 起',
        '在「範例飯店」的 100 則評論中獲得 4.5 顆星',
        '在「測試旅館」的 2,000 則評論中獲得 4.1 顆星',
    ],
    'en': [
        'Prices starting from $123, Example Hotel DEAL 25% less than usual',
        'Prices starting from $246, Testing Inn',
        '4.5 out of 5 stars from 100 reviews, Example Hotel',
        '4.1 out of 5 stars from 2,000 reviews, Testing Inn',
    ],
    'ja': [
        'サンプルホテル、NT$1,234～ 大変お得 通常より 25% お得',
        'テスト旅館、NT$2,468～',
        '100 件の評価で 4.5 つ星（最高は 5 つ星）（サンプルホテル）',
        '2,000 件の評価で 4.1 つ星（最高は 5 つ星）（テスト旅館）',
    ],
}


def as_page(labels):
    """把 label 清單包成 parser 吃得下的 HTML 片段。

    parser 只找 aria-label 屬性，所以不需要完整文件結構；刻意加上幾個無關的
    aria-label 與 HTML 雜訊，確保 parser 真的在挑選而不是照單全收。
    """
    noise = ['<div aria-label="搜尋"></div>',
             '<button aria-label="Not selected, Price filter"></button>',
             '<span aria-label="メニュー"></span>']
    body = ''.join(f'<div aria-label="{lab}"></div>' for lab in labels)
    return '<html><body>' + ''.join(noise) + body + '</body></html>'
