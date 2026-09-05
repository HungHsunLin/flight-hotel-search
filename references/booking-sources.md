# 抓訂購來源（官網 vs OTA）

`curl` 拿得到「有哪些航班、多少錢」，但拿不到「這個價格是誰在賣」。訂購選項那一層是 client-side 用 `batchexecute` RPC 動態載入的——實測 curl 那個 1.49MB 的 booking 頁，`Agoda` / `Gotogate` / 價格一個都沒有。所以這層只能用瀏覽器。

用 Playwright MCP（`mcp__plugin_playwright_playwright__*`）。chrome-devtools MCP 也可以，但它會接管使用者正在用的 Chrome，比較擾民。

## 機票的操作序列

Google Flights 是三層頁面：搜尋結果 → 選去程 → 選回程 → 訂購選項。來回票必須走完四步，沒有捷徑。

### 1. 導到搜尋頁

```
mcp__plugin_playwright_playwright__browser_navigate
url: https://www.google.com/travel/flights?q=Flights%20from%20TPE%20to%20TYO%20on%202026-10-01%20through%202026-10-05&curr=TWD&hl=zh-TW
```

用 URL query 帶入條件，不要去點 UI 填表單——Google 的日期 picker 很難用 selector 穩定操作，而 `q=` 參數一發就到位。

### 2. 選去程

用文字 selector 點，不要用 class（Google 的 class 是混淆過的亂碼如 `.mxvQLc`，會隨版本變）：

```
target: li:has-text("<航空公司>"):has-text("<價格>") >> nth=0
```

點完頁面標題會從「臺北市到東京都」變成「東京都到臺北市」，代表進到回程選擇了。

### 3. 選回程

回程列表的 ref 每次都不同，先抓一次淺 snapshot（`depth: 8`）拿 ref，再點。這裡就能看到「分段購票」標記——如果每一筆都標著它，代表這個組合全都是拼湊的獨立票。

### 4. 讀訂購選項

到 `/travel/flights/booking` 後，抓 snapshot 並存檔（`filename` 參數），再用 grep 取出來源清單。這頁 snapshot 很大，直接吐回 context 會浪費大量 token：

```bash
grep -n "透過.*預訂\|航空公司$\|\$[0-9],[0-9]" <snapshot.yml>
```

檔案會存在 `~/.playwright-mcp/`，用 `ls -t | head -1` 拿最新的。

**只抓 aria-label 會漏掉展開後才出現的通路。** 實測華航頁的 Gotogate、虎航頁的 Expedia /
Mytrip / eDreams 都不在 aria-label 裡。一次實際查詢照這個方法做，得出「這條航線零 OTA」
的結論——是錯的，重驗後每一頁都有三到四個 OTA。展開之後要改掃 `document.body.innerText`
的「透過…預訂」句式才完整。

**展開鈕會被 overlay 攔截。** `browser_click` 點「查看其他選項」會 timeout；改用
`browser_evaluate` 直接對元素呼叫 `el.click()` 就能繞過。

**分段購票標記只在這一層看得到。** 回程選擇頁 find「分段購票」實測 34 筆，而 `curl` 抓的
搜尋首屏一筆都沒有——`gfparse.py` 也不解析它。所以**腳本輸出沒有這個標記，不代表沒有
分段購票**。

順帶一個實測到的反直覺情況：OTA 有時會把航空公司的**單一張來回票拆成分段購票**賣。
Gotogate 的虎航來回 NT$10,974 比官網的 NT$10,622 貴，商品卻更差——多付錢換到兩張獨立票。

## 怎麼判別官網 vs OTA

Google 在航空公司官網那筆旁邊掛一個**獨立的 badge 元素**，內容是「航空公司」：

```yaml
- generic:
    - text: 透過<航空公司名>預訂
    - generic: 航空公司        # ← 這個 badge 只有官網選項才有
  - generic: <價格>
```

OTA 選項沒有這個 badge：

```yaml
- generic: 透過<OTA 名>預訂
  - generic: 透過相同的供應商分段購票
- generic: <價格>
```

aria-label 也有語意差異可以佐證：官網那筆的句尾帶「**航空公司**」這個詞（形如「繼續以 <價格> 的票價透過 <航空公司名> 航空公司預訂」），OTA 那筆則是「透過「<OTA 名>」預訂」的句式，沒有「航空公司」這個詞。

**不要用「來源名稱裡有沒有航空公司的名字」去比對**——OTA 的名稱也可能含航空公司字樣，而且 code-share 的情況下官網那筆會列出兩三家航空公司的名字，字串比對很容易誤判。抓 badge 的存在與否才穩定。

清單預設只顯示 5 筆，底下有「其他 N 個預訂選項」的按鈕，要展開才完整。

## 一次實測的完整結果

TPE→TYO 一組來回日期，某全服務航空去程 + 某廉航回程：

| 來源 | badge | 價格 | 購票方式 |
|---|---|---|---|
| 航空公司官網（兩家聯營） | **航空公司** | $8,696 | 分段購票，2 張票分別訂 |
| Agoda | — | $8,791 | 同供應商分段購票 |
| ly.com（同程旅行） | — | $9,076 | 同供應商分段購票 |
| Jettzy | — | $9,087 | 同供應商分段購票 |
| Gotogate | — | $9,526 | 同供應商分段購票 |
| Mytrip | — | $9,527 | 同供應商分段購票 |

這次官網最便宜，但不能當通則——OTA 有時會用補貼把價格壓到官網以下，特別是大促期間。所以這層才需要實際去看，不能靠經驗推測。

要注意的是：**OTA 便宜個一兩百塊時，官網通常仍然是較好的選擇**。退改簽直接跟航空公司處理、行李加購不會出問題、航班異動時你在航空公司的系統裡是有名字的旅客而不是一筆代訂紀錄。這個差異在出事時才會顯現，值得主動跟使用者講。

## 飯店的訂購來源

同樣的道理，飯店頁點進單一飯店後會列出 Booking.com / Agoda / 飯店官網等通路的比價，一樣是動態載入。操作方式：導到飯店頁 → 點「價格」分頁 → 抓 snapshot → grep 來源與價格。

**但 Google 上那一個「官網」數字不能當成官網的結論。** Google 每個通路只顯示一個數字，而官網賣的是**一整組方案**。實測某大阪商務飯店（5 晚、1 人）：Google 顯示官網 NT$2,574/晚，點進官網後同一間房有 **21 種方案**，5 晚總價從 NT$12,858 到 NT$25,475，差近一倍：

| 官網方案 | 會員價(5晚) | 標準價(5晚) |
|---|---|---|
| 早鳥優惠（僅客房） | 12,858 | 14,286 |
| 連住 2 晚以上折扣 | 13,042 | 14,490 |
| 基礎住宿／隨時免費取消 | 13,317 | 14,797 |
| 含自助早餐 | 14,512 | 16,124 |
| 含 1000 日圓禮券＋延遲退房 | 14,695 | 16,328 |

而且**會員價與標準價差約 10%，會員價要註冊登入才拿得到**。這次 Google 顯示的 2,574×5＝12,870 剛好對應「會員早鳥」12,858——也就是說 Google 顯示的已經是要登入才享有的價格，不是隨手點進去就有的價格。

所以流程是：Google 抓出「有哪些通路、大致落點」→ **實際進官網展開全部方案**（頁面上通常有「顯示全部的住宿方案 (N件)」要點開，預設只露出幾個「推薦」方案，而推薦方案往往不是最便宜的）→ 才能跟 OTA 比。

比的時候還要對齊三件事，否則是在比不同商品：
- **房型**：官網可能只剩雙床房，OTA 卻還在賣單人房，兩者坪數與價格本來就不同
- **含不含早餐**：同一間房差 NT$1,200～1,600（5 晚）
- **取消條件**：官網早鳥通常不可取消，OTA 常附免費取消到入住前幾天

官網的隱形價值也不會出現在數字上：會員點數、延遲退房、備品、升等機會、出事時直接跟飯店談。OTA 則常有平台回饋或信用卡加碼。金額大的時候值得兩邊都展開看。

## 什麼時候不值得做這一步

這層要花 15 秒左右，還會開瀏覽器。使用者只是在抓預算、比日期、看行情時，不要主動跑——直接給 `curl` 的結果就好。

值得跑的時機很明確：使用者準備下訂了、明確問「官網比較便宜嗎」、或金額大到值得為幾百塊多花一分鐘確認。

## 飯店品牌的直接資料來源（繞過瀏覽器）

以下都是 2026-09-02 在本機實測的結果。**沒有實測到的部分明確標為未驗證**，不要當事實引用。

### Dormy Inn 系：公開 JSON API，不需要任何 token

```
https://dormy-hotels.com/reserve/api/hotels
  ?keyword=&keyword_reference=&checkin=2026/09/12
  &number_of_nights=1&number_of_rooms=1&search_by_tag=hotel
  &tags=&brands=&order_by=&stock_check=true
  &number_of_adults[]=1
  &number_of_children_need_futons[]=0&number_of_children_no_need_futons[]=0
  &page=1
```

回 `{message, data:{total, per_page:10, data:[…], next_page}}`。實測 `total` 為 145~146
（全品牌，含 野乃、ラビスタ），一頁 10 筆，所以 15 個請求可取全量。

**最有價值的是 `inventories`**：它不是只回你問的那幾晚，而是自 `checkin` 起算約兩週的
逐日房價與剩房數。一次呼叫就能算出整段期間的所有窗口，不必逐組日期查。

**但回應 schema 由參數完整度決定——這是個會讓 parser 安靜壞掉的坑：**

| 送出的參數 | `inventories` 型別 | 筆數 | 日期鍵 |
|---|---|---|---|
| 上列完整參數 | `list` | 15 | `month_day: '09/12'` |
| 少送任何一個 | `dict` | 14 | ISO 日期 `'2026-09-12'` |

實測是決定性的（各跑 3 次，3/3 一致），而且**沒有任何單一參數能翻轉它**——逐一補回
`keyword_reference` / `tags` / `brands` / `order_by` / 兩個 `children[]` 都仍是 dict，
六個全補齊才變回 list。所以：**照上面那份完整參數送**，同時 parser 兩種都要處理。

`list` 形態每筆長這樣：
```json
{"day_name":"土","month_day":"09/12","year":"2026","icon":"circle",
 "price":29850,"number_of_room_remain":"残り18部屋から表示","stock":18,
 "is_holiday":0,"is_available":true}
```

**兩條 peer 回報的坑，本檔案複驗不成立**（記在這裡，免得後人照著繞路）：

- 「`keyword=` 靜默失效」——實測**有效**：`keyword=熊本` 回 `total=3`，三筆全是熊本県
  （六花の湯ドーミーイン熊本、御宿 野乃熊本、ラビスタ南阿蘇）。
- 「`stock_check=false` 會讓所有 price 變 0，看起來像整區滿房」——實測 `true` 與 `false`
  回傳的價格**逐筆相同**（29850 / 9450 / 18720 …）。
- 「curl 必須加 `--globoff`，否則方括號被當 glob 而不發請求」——實測加不加都拿到相同
  的 103200 bytes。加上去無害，但它不是本機失敗的原因。

差異可能來自對方組 URL 的方式，不代表對方看錯；只是**照本節這份 URL 不會踩到**。

### tripla（VIA INN、大和ROYNET 共用）：需要 client-session JWT

直接打會被擋，實測回應：

```
HTTP 400
{"data":null,"errors":[{"title":"You don't have permission to access this",
 "details":{"system":[{"error":"You don't have permission to access this","code":1000}]}}]}
```

（另一個 session 回報的訊息是 `Client-Session is required`，與本機看到的不同——推測隨端點
或版本而異。）

**未驗證**：JWT 可從瀏覽器載入官網訂房頁攔 request header 取得（匿名、不需登入）、品牌分館
清單端點 `hotel_brands/{id}/hotels`、以及 VIA INN=1152 / 大和ROYNET=95 這兩個 brand id。
要用之前請自行驗證。

### 大和ROYNET 館別 code

```bash
curl -s https://www.daiwaroynet.jp/<slug>/ | grep -oE 'value="[0-9a-f]{32}"' | sort -u | head -1
```

訂房 URL 的館別參數名是 `code=`，不是 `hotel_id=`——**未驗證**（peer 回報用錯參數名會導向
推薦頁並顯示「未能搜到有空房」，也就是產生一個看起來完全合理的假滿房結論）。

peer 另外警告「不限定 `value=` 直接抓 32 hex 會在多館之間抓到同一個共用字串」——在
`hakata-gion` 上**複驗不成立**：限定與不限定兩種寫法抓到的前三筆完全相同。

### 會員制度的歸屬必須查證，不能從母公司推論

ヴィアイン 由 **株式会社JR西日本ヴィアイン**（ジェイアール西日本デイリーサービスネット
100% 子公司）經營，**不屬於 JRホテルグループ，也不屬於 JR西日本ホテルズ**，只是偶爾聯合
行銷。ヴィアインメンバーズクラブ 與 JRホテルメンバーズ 是兩套獨立的會員制度。

一般規則：**同集團 ≠ 同會員制度**。使用者說「我有 X 的會員」時，能不能涵蓋 Y 品牌要實際
查證，從母公司關係推論會推錯。
