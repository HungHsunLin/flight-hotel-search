#!/bin/bash
# gflight.sh FROM TO DEPART [RETURN] [AIRLINE]
#
# AIRLINE 是選填的航空公司篩選，**必須用當前語系介面的寫法**（hl=zh-TW 下「中華航空」
# 有效、'China Airlines' 回 0 筆；hl=en 下反過來）。一次只能指定一家，多家並列會查不到；
# 要比多家就分別呼叫。這個篩選會同時套用到去程與回程——見 gnolcc.py 的說明。
#
# 語系/幣別/地區用環境變數控制，預設 zh-TW / TWD / tw：
#   GFH_LANG=en GFH_CURR=USD ./gflight.sh Taipei Tokyo 2026-10-01 2026-10-05
D="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
. "$D/_common.sh"

[ $# -lt 3 ] && { _msg "用法: $(basename "$0") 出發地 目的地 YYYY-MM-DD [回程] [航空公司]" \
                        "Usage: $(basename "$0") FROM TO YYYY-MM-DD [RETURN] [AIRLINE]"; exit 1; }
_check_date_format "$3" || exit 1
_check_not_past "$3" "$(_msg 出發日 'departure date')" || exit 1

Q="Flights from $1 to $2 on $3"; [ -n "$4" ] && Q="$Q through $4"
[ -n "$5" ] && Q="$Q $5"
curl -sL -A "$GFH_UA" \
  --get --data-urlencode "q=$Q" --data-urlencode "curr=$GFH_CURR" \
  --data-urlencode "hl=$GFH_LANG" --data-urlencode "gl=$GFH_REGION" \
  'https://www.google.com/travel/flights' | python3 "$D/gfparse.py"
