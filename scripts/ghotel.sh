#!/bin/bash
# ghotel.sh 地點 入住 退房 [成人數] — 查 Google Hotels（不需瀏覽器）
# 例: ghotel.sh 京都 2026-11-24 2026-11-26 2
#     GFH_LANG=en GFH_CURR=USD ./ghotel.sh Kanazawa 2026-11-24 2026-11-26 2
D="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
. "$D/_common.sh"

[ $# -lt 3 ] && { _msg "用法: $(basename "$0") 地點 YYYY-MM-DD YYYY-MM-DD [成人數]" \
                        "Usage: $(basename "$0") PLACE YYYY-MM-DD YYYY-MM-DD [ADULTS]"; exit 1; }
for ARG in "$2" "$3"; do _check_date_format "$ARG" || exit 1; done
_check_not_past "$2" "$(_msg 入住日 'check-in date')" || exit 1
_check_horizon "$2"

# 幣別必須傳進 ts：實測 URL 的 curr= 對 Hotels **完全無效**，真正生效的是 ts protobuf
# 裡的幣別欄位。少傳這個參數，不管 curr= 寫什麼都固定回 TWD 報價。
TS=$(python3 "$D/gtsgen.py" "" "" "$2" "$3" "${4:-2}" "$GFH_CURR") || exit 1
if [ -z "$TS" ]; then
  _msg "錯誤：ts 參數產生失敗，中止查詢。" "Error: failed to build ts parameter, aborting." >&2
  _msg "（若照常送出，Google 會用預設日期回一頁看似正常但日期完全不對的結果）" \
        "(Sending it anyway would return a normal-looking page for the WRONG dates.)" >&2
  exit 1
fi

# 把要求的晚數傳給 parser 對帳：超出可訂範圍時 Google 會靜默改回單晚行情，
# 而那頁的每晚房價單看完全正常，不比對晚數就發現不了。
NIGHTS=$(_days_between "$2" "$3")
Q=$(python3 "$D/locales.py" hotel_query "$GFH_LANG" "$1")
curl -sL -A "$GFH_UA" \
  --get --data-urlencode "q=$Q" --data-urlencode "hl=$GFH_LANG" \
  --data-urlencode "gl=$GFH_REGION" --data-urlencode "curr=$GFH_CURR" \
  --data-urlencode "ts=$TS" \
  'https://www.google.com/travel/search' \
  | python3 "$D/ghparse.py" --expect-nights "$NIGHTS"
