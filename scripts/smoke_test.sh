#!/bin/bash
# 三系统冒烟测试 - 部署后自动执行
# 用法: bash smoke_test.sh

PASS=0
FAIL=0

check() {
    local name=$1 url=$2 expected=$3
    local code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$url" 2>/dev/null)
    if [ "$code" = "$expected" ]; then
        echo "  ✅ $name"
        PASS=$((PASS+1))
    else
        echo "  ❌ $name (got $code, expected $expected)"
        FAIL=$((FAIL+1))
    fi
}

echo "=== 三系统冒烟测试 ==="

check "酒店首页" "https://7yijia888.com/" "200"
check "景区首页" "https://7yijia888.com/scenic/" "200"  
check "公寓健康" "https://7yijia888.com/apartment/health" "200"
check "酒店登录" "https://7yijia888.com/admin/pages/login.html" "200"
check "景区登录" "https://7yijia888.com/scenic/admin/pages/login.html" "200"
check "VIP备案" "http://yijia888vip.me/" "200"

echo ""
echo "通过:$PASS 失败:$FAIL"
exit $FAIL
