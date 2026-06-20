#!/bin/bash
# 景区系统一键恢复脚本
set -e
SERVER="ubuntu@111.229.30.253"
PASS="yjr4001889468YJR"
echo "=== 景区管理系统恢复 ==="
echo "1/3 拉取代码..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$SERVER" \
  "cd /home/ubuntu/scenic && git pull origin main"
echo "2/3 重启后端..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$SERVER" \
  "kill \$(lsof -ti:8002) 2>/dev/null; sleep 1; cd /home/ubuntu/scenic/backend && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/scenic.log 2>&1 &"
sleep 3
echo "3/3 验证..."
curl -sk -o /dev/null -w "  后端: %{http_code}\n" https://7yijia888.com/scenic/
echo "完成! https://7yijia888.com/scenic/admin/"
echo "账号: admin / admin123"
