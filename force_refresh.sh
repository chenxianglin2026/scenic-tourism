#!/bin/bash
# 景区系统 - 强制刷新脚本
# cron每5分钟执行deploy-all.sh后调用此脚本

echo "$(date): Force-refreshing scenic..." >> /tmp/deploy-all.log

# 1. 完全停掉scenic
systemctl stop scenic 2>/dev/null
kill -9 $(lsof -ti:8002) 2>/dev/null
sleep 2

# 2. 清理所有Python缓存
find /home/ubuntu/projects/scenic -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /home/ubuntu/projects/scenic -name "*.pyc" -delete 2>/dev/null

# 3. git pull from Gitee
cd /home/ubuntu/projects/scenic/code
git stash 2>/dev/null
git pull https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/scenic-tourism.git main

# 4. 确认文件就位
if grep -q "bookings" backend/app/main.py; then
    echo "$(date): Scenic code verified OK" >> /tmp/deploy-all.log
fi

# 5. 启动
cp -f admin/pages/*.html /home/ubuntu/projects/scenic/admin/pages/ 2>/dev/null
systemctl start scenic
sleep 3

# 6. 验证
TEST=$(curl -s http://127.0.0.1:8002/api/hotels/_test 2>/dev/null)
echo "$(date): Scenic _test=$TEST" >> /tmp/deploy-all.log
