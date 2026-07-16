#!/bin/bash
# 三系统定时健康检查 - 异常时通知
LOG=/tmp/health_check.log
FAILS=""

for name url expected in \
    "酒店" "https://7yijia888.com/" 200 \
    "景区" "https://7yijia888.com/scenic/" 200 \
    "公寓" "https://7yijia888.com/apartment/health" 200 \
; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 8 "$url" 2>/dev/null)
    if [ "$code" != "$expected" ]; then
        FAILS="$FAILS $name=$code"
    fi
done

if [ -n "$FAILS" ]; then
    echo "$(date): ❌ HEALTH FAIL$FAILS" >> $LOG
else
    echo "$(date): ✅ all ok" >> $LOG
fi
