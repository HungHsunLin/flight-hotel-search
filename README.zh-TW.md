# flight-hotel-search

[English](README.md) · **繁體中文** · [日本語](README.ja.md)

[![tests](https://github.com/HungHsunLin/flight-hotel-search/actions/workflows/tests.yml/badge.svg)](https://github.com/HungHsunLin/flight-hotel-search/actions/workflows/tests.yml)

從 Google Flights / Google Hotels 抓即時機票票價與飯店房價。可以當
[Claude Code](https://claude.com/claude-code) skill 用，也可以單獨執行 CLI 腳本。

**核心洞察：** Google 把首屏結果 server-side render 進 HTML，所以大多數查詢用 `curl` 就夠——
比開瀏覽器快約 20 倍。只有「這個價格是誰在賣」那一層是動態載入的，才需要真正的瀏覽器。

支援**繁體中文、英文、日文**三種介面，幣別可獨立設定。

## 環境需求

`bash`、`curl`、`python3`。無第三方套件、無 API key、不需編譯。

已在 CI 上驗證：Linux 搭配 Python 3.9、3.11、3.13、3.14，以及 macOS 搭配 3.14。程式碼未使用
版本相依語法，shell 腳本也避開了 GNU 與 BSD 之間有差異的 `date` flag（CI 會實際驗證過去日期
的防呆在每個平台上都真的觸發，而不是被靜默跳過）。

## 快速開始

```bash
# 預設語系就是 zh-TW，以下不需額外設定；要換成英文或日文介面見「語系與幣別」。

# 來回（用城市名可涵蓋該都會區所有機場）
scripts/gflight.sh 臺北市 東京都 2026-10-01 2026-10-05

# 單程（省略回程日）
scripts/gflight.sh TPE KIX 2026-11-15

# 飯店：地點 入住 退房 成人數
scripts/ghotel.sh 京都 2026-11-24 2026-11-26 2

# 掃描區間找最便宜的日子
python3 scripts/gscan.py flight TPE TYO 2026-10-01 2026-10-31 --nights 4
python3 scripts/gscan.py hotel 京都 2026-11-20 2026-11-30 --nights 2

# 只查全服務航空的來回票（為什麼需要獨立腳本見「陷阱」）
python3 scripts/gnolcc.py 臺北市 大阪 2026-03-15 2026-03-20
```

### 訂購來源（官網 vs OTA）

「這張票是誰在賣」是唯一**不會** server-side render 的一層，所以需要真正的瀏覽器自動化，
`curl` 拿不到。完整流程見
[`references/booking-sources.md`](references/booking-sources.md)，該文件是為 Claude Code skill
撰寫的（透過 MCP 驅動瀏覽器）。只用 CLI 腳本的話用不到這層。

## 語系與幣別

全部由環境變數控制，預設為 `zh-TW` / `TWD` / `tw`。

| 變數 | 預設 | 說明 |
|---|---|---|
| `GFH_LANG` | `zh-TW` | `zh-TW`、`en`、`ja` |
| `GFH_CURR` | 跟著語系 | 與語系互相獨立，見下方 |
| `GFH_REGION` | 跟著語系 | Google 的 `gl` 參數 |
| `GFH_UA` | 一般瀏覽器字串 | 要改用自訂識別時設定 |

```bash
GFH_LANG=en scripts/gflight.sh Taipei Tokyo 2026-10-01 2026-10-05
GFH_LANG=ja scripts/ghotel.sh 金沢 2026-11-24 2026-11-26 2

# 語系與幣別互相獨立：中文介面、日圓報價
GFH_LANG=zh-TW GFH_CURR=JPY scripts/ghotel.sh 京都 2026-11-24 2026-11-26 2
```

用 `GFH_LANG=ja` 查日本飯店，通常能拿到比英文介面更完整的在地飯店名與更多本地業者。

## 運作方式

Google 把結果資料寫進 `aria-label` 屬性，形式是**自然語言句子**，而各語系的語序完全不同：

```
zh-TW  來回總價 <price> 新台幣起。 搭乘<airline>的直達航班。 … 於<airport>出發，…
en     From <price> US dollars round trip total. Nonstop flight with <airline>. Leaves <airport> …
ja     往復の合計金額 <price> 円～。 <airline> が運航する直行便。 … <airport>発、…
```

飯店更極端——價格與名稱的前後位置是相反的：

```
zh-TW  <hotel>，價格 $<price> 起                 <- 名稱在前
en     Prices starting from $<price>, <hotel>     <- 價格在前
ja     <hotel>、NT$<price>～                       <- 名稱在前
```

所以不可能用一組通用 regex 覆蓋。`scripts/locales.py` 為每個語系各存一組樣式，並使用具名
群組（`name`、`price`、`dep`、`arr`…），讓 parser 本身與語言無關。

## 陷阱

以下這些會**算出錯誤的數字卻不報任何錯**，比直接壞掉危險得多。全部是實際比對回應差異
發現的，不是讀文件推的。

**Google 對不認識的參數會安靜忽略。** 它不會回 400，而是直接用預設值算給你。所以任何時候
你自己組查詢參數，都要做對照組：換一個「應該產生明顯差異」的輸入（跨年 vs 隨便一個週二）。
如果結果沒變，那個參數就沒生效。

**飯店的日期與幣別藏在 `ts=` protobuf 裡，不在 URL 參數。** 寫
`?checkin=2026-12-30&checkout=2027-01-03` 會回一整頁看起來完全正常、但其實是**明天住一晚**
的結果。同理 `curr=USD` 對飯店無效——真正生效的是 `ts` 裡的幣別欄位。實測同一間飯店：
假日期 1,348 vs 真跨年 4 晚 4,207，差 3.1 倍。`scripts/gtsgen.py` 會正確生成 `ts`，走腳本
就不會踩到。

**人數是用「重複欄位的次數」編碼，不是寫個數字。** 一位成人是一組 `{1:{1:3}}`，兩位就重複
兩次。把數字寫進某個欄位會被安靜忽略，一律回 2 人房價。單人房價通常便宜兩三成。

**「來回總價 X 起」只代表去程的航空公司。** 那個價格是配上最便宜回程算出的下限，而最便宜
的回程往往是廉航。所以拿結果清單過濾航空公司，濾掉的只有去程。`gnolcc.py` 就是為此而存在：
它把航空公司名塞進查詢字串，Google 會把篩選**同時套用到兩個航段**。實測 TPE-KIX：清單顯示
某全服務航空 11,711，實際是該航空去程 + 廉航回程；兩段都是同一家的真實來回票是 13,819。

**航空公司名必須符合當前介面語言。** `China Airlines` 在 `hl=zh-TW` 下回 0 筆，`中華航空`
在 `hl=en` 下也回 0 筆。`locales.py` 為每個語系存了對應名單，而且一次只能篩選一家。

**飯店價格是每晚房價，不是住宿總額**，而且掃描器是依**中位數**而非最低價排序——最低價那筆
通常是青旅或膠囊，某天冒出一個便宜床位會讓那天看起來最划算，實際上整體行情很貴。

**Google 不等於全市場。** 它列的是合作 partner。廉航自家官網的限時促銷、許多區域型 OTA
都不會出現。「Google 上最便宜」不等於「市場最便宜」。

**只有首屏會 server-side render**——大約 20-24 筆航班、18-20 間飯店。抓行情足夠，但不是
完整清單。

## 測試

```bash
python3 -m unittest discover -s tests -v
```

35 個測試，不需網路、不需第三方 test runner。全部跑在 `tests/fixtures.py` 的**合成資料**上
（虛構的航空公司、飯店與價格，如 `Example Air`、`範例航空`）。只有機場名是真實的，因為那
正是對照表要驗證的目標，而地名是事實。

有兩件事值得理解：

- 這套測試驗證的是**我們的 regex 有沒有照設計運作**，不是 Google 的輸出是否仍然符合。
  如果 Google 改寫了 label，測試會全綠但線上查詢回空。所以改動 `locales.py` 的樣式時，
  必須另外用真實頁面驗證一次。
- 版本庫裡不存放任何來源網站的頁面內容。把真實 HTML 存成 fixture 是最省事的做法，但那等於
  把別人的頁面 commit 進版本庫。

多數 case 對應實際發生過的 bug，測試名稱或註解裡都有標明。整套測試經過變異測試驗證——
把四個歷史 bug 重新植入（被吞掉的 `DEAL` 尾綴、過小的 label 上限、`ts` 漏掉幣別、移除 CJK
寬度計算），每一個都會讓測試變紅。

每次 push 與 pull request，CI 都會在 Linux 與 macOS 上跑整套測試——見
[`.github/workflows/tests.yml`](.github/workflows/tests.yml)。CI **不執行任何實際查詢**：
從共用的 CI runner 發送自動化請求，性質與個人在本機執行 CLI 完全不同，而且那些 IP 很快就會
被限流，會讓測試變得時好時壞。代價是來源網站改變輸出格式時 CI 仍會全綠，那一層只能靠實際
使用時發現。

## 新增語系

1. 複製 `scripts/locales.py` 裡 `LOCALES` 的一組條目。
2. **實際抓一次該語系的頁面**，把真實的 `aria-label` 字串跟你的樣式比對。不要照文法直覺寫。
3. 確認 parser 回傳筆數大於 0。Google 不會回報解析失敗——你只會拿到空清單，而那跟「地名
   打錯」「被限流」長得一模一樣。

新增語系時要注意兩件事。英文 label 比 CJK 長得多（實測直飛航班：英文 233-277 字元、中文
108-131），所以擷取長度上限必須逐語系設定——上限設得太小會安靜地切掉句尾（抵達時間、
總時長），完全不報錯。另外英文會把貨幣拼成全名（`From <price> US dollars`）而不用符號，
所以用 `$` 比對會一筆都找不到。

## 當作 Claude Code skill 使用

這個版本庫同時也是一個 [Claude Code](https://claude.com/claude-code) skill。把整個目錄放進
`~/.claude/skills/`，CLI 就會載入它。

| 檔案 | 用途 |
|---|---|
| `SKILL.md` | Claude Code 載入的 skill 定義，以繁體中文撰寫。 |
| `SKILL.en.md` | 英文版。**要使用的話把兩個檔名對調**——Claude Code 只讀 `SKILL.md`。 |
| `evals/evals.json` | skill 的觸發與行為評估，格式為 Claude Code `skill-creator` 所使用。這不是單元測試套件，使用 CLI 腳本也不需要它；其中的 prompt 為中文，且假設台灣出發的旅遊脈絡。 |
| `references/local.md` | **選用，不進版本庫。** 建立此檔後，`SKILL.md` 會指示 Claude 讀取它。用途是放本機專屬的銜接設定——你自己的哪個 skill 負責把結果寫進行程文件、你的檔案慣例，以及任何不該寫死進公開版本庫的東西。 |

skill 定義刻意不指名要交接給誰：它只說結果應該交給「負責管理那些文件的 skill」。把具體
設定放在被 ignore 的 `references/local.md`，可以讓公開的 skill 保持可移植，同時你自己的
設定維持私有。

CLI 腳本可獨立運作，不需要上述任何檔案。

## 支援與維護

以 best-effort 方式維護，不保證支援或回應時間。

請理解這個專案依賴什麼：parser 讀的是 Google 的渲染輸出，所以**對方改動措辭或標記就會壞掉，
而且是靜默失敗**——查詢回空清單而不是報錯。這是「何時」而非「是否」的問題。如果結果突然
變空，先拿 `locales.py` 對照新抓的頁面，再判斷是不是限流。

歡迎附上可重現查詢的 bug 回報。歡迎新增語系的 pull request，前提是遵循「新增語系」的流程——
特別是樣式必須用真實頁面驗證過，且不得 commit 任何擷取到的頁面內容。

## 法律聲明

本工具僅供**個人研究與學習用途**。它讀取公開可存取的頁面並擷取事實性資料（價格、時間、
評分）；不快取、不轉售、不重新散布任何內容。

使用者需自行確認其使用方式符合所查詢網站的服務條款與所在地法令。Google 的服務條款禁止對
其服務進行自動化存取。作者以現狀提供本軟體，不對使用結果負任何責任。

請勿將本工具部署為公開的 hosted API 或爬蟲服務。自己跑 CLI 與經營商業爬蟲端點，在法律上
與倫理上都是截然不同的兩回事。

## 授權

Apache License 2.0——見 [LICENSE](LICENSE)。
