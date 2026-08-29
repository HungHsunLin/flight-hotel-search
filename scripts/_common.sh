# 共用設定，被 gflight.sh / ghotel.sh source。不直接執行。
#
# 全部可用環境變數覆寫，未設定時維持 zh-TW / TWD / tw——與加入多語支援前的行為一致，
# 既有用法不受影響。

GFH_LANG="${GFH_LANG:-zh-TW}"

# 幣別與地區預設跟著語系走，但可以各自覆寫（例如想用中文介面看日圓報價：
# GFH_LANG=zh-TW GFH_CURR=JPY）。
case "$GFH_LANG" in
  en) GFH_CURR="${GFH_CURR:-USD}"; GFH_REGION="${GFH_REGION:-us}" ;;
  ja) GFH_CURR="${GFH_CURR:-JPY}"; GFH_REGION="${GFH_REGION:-jp}" ;;
  *)  GFH_CURR="${GFH_CURR:-TWD}"; GFH_REGION="${GFH_REGION:-tw}" ;;
esac
export GFH_LANG GFH_CURR GFH_REGION

# User-Agent。預設是一般瀏覽器字串：Google 對非瀏覽器 UA 會回不同結構的頁面，
# 解析會直接拿到空結果。要改用自訂識別字串（例如公開部署時表明來源）就設 GFH_UA。
GFH_UA="${GFH_UA:-Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36}"

# 依語系輸出訊息：第一個參數中文、第二個英文。
_msg() { case "$GFH_LANG" in zh*) printf '%s\n' "$1" ;; *) printf '%s\n' "$2" ;; esac; }

# 日期防呆。刻意用字串比較而不是 date 轉 epoch：`date -j` 是 macOS/BSD 語法、
# `date -d` 是 GNU 語法，寫死任一種在另一個平台上會靜默失敗（epoch 取到空值，
# 比較被跳過）。YYYY-MM-DD 的字典序恰好等於時間序，零成本且到處都能跑。
_check_date_format() {
  case "$1" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) return 0 ;;
    *) _msg "錯誤：日期格式須為 YYYY-MM-DD，收到: [$1]" \
             "Error: date must be YYYY-MM-DD, got: [$1]" >&2
       _msg "（常見原因：呼叫端字串沒引號，兩個日期被當成同一個參數）" \
             "(Common cause: unquoted argument merged two dates into one)" >&2
       return 1 ;;
  esac
}

# 查過去的日期，Google 就是安靜地回空結果——跟「機場代碼打錯」「被限流」長得一模一樣。
# 沒有這個檢查，呼叫端會以為腳本壞了去除錯 curl/編碼，其實只是年份選錯（常見於
# 「2月初」這種沒講年份、而那個月今年已經過了的說法）。
# 注意：緊接 CJK 全形標點的變數一律寫成 ${var}。在 zh_TW.UTF-8 之類的 locale 下，
# bash 會把全形右括號「）」的首位元組吃進變數名，$today） 於是展開成不存在的變數
# （空字串），畫面上只剩兩個亂碼位元組。半形 ) 不是變數名合法字元所以不受影響——
# 這個 bug 只在中日文訊息裡出現，英文訊息完全正常，極易漏看。
_check_not_past() {
  local today; today="$(date +%Y-%m-%d)"
  if [[ "$1" < "$today" ]]; then
    _msg "錯誤：$2 $1 已經是過去的日期（今天是 ${today}）。" \
          "Error: $2 $1 is in the past (today is ${today})." >&2
    _msg "使用者說的月份如果沒講年份、且那個月今年已經過了，該用明年，不是今年。" \
          "If the user gave a month with no year and it has already passed, use next year." >&2
    return 1
  fi
}
