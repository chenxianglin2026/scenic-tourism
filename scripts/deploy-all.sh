#!/bin/bash
# 三系统部署 - 极简版 v3.0
# root cause fix: 清pyc → git pull → systemctl restart
LOG=/tmp/deploy-all.log
echo "$(date): deploy" >> $LOG

# === 酒店 (systemd→git, 套娃路径) ===
cd /home/ubuntu/yijiaren/code 2>/dev/null && {
    find . -name __pycache__ -exec rm -rf {} + 2>/dev/null
    sudo git pull https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/yijiaren-hotel.git main >> $LOG 2>&1
    sudo systemctl restart yijiaren 2>/dev/null
    echo "$(date): Hotel done" >> $LOG
}

# === 景区 (systemd→git) ===
cd /home/ubuntu/projects/scenic/code 2>/dev/null && {
    find . -name __pycache__ -exec rm -rf {} + 2>/dev/null
    sudo git pull https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/scenic-tourism.git main >> $LOG 2>&1
    sudo systemctl restart scenic 2>/dev/null
    echo "$(date): Scenic done" >> $LOG
}

# === 公寓 (systemd→git) ===
cd /home/ubuntu/apartment/code 2>/dev/null && {
    find . -name __pycache__ -exec rm -rf {} + 2>/dev/null
    sudo git pull https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/apartment-mgr.git main >> $LOG 2>&1
    sudo systemctl restart apartment 2>/dev/null
    echo "$(date): Apartment done" >> $LOG
}

# === VIP站点 ===
sudo mkdir -p /var/www/vip 2>/dev/null
[ ! -f /var/www/vip/index.html ] && echo '<!DOCTYPE html><html><head><meta charset=UTF-8><title>伊家智能科技</title></head><body style=text-align:center;padding:80px><h2>伊家智能科技</h2><p>智慧酒店·智慧景区·长租公寓</p><p><a href=https://beian.miit.gov.cn>粤ICP备16027093号</a></p></body></html>' | sudo tee /var/www/vip/index.html > /dev/null

sleep 3
echo "$(date): verify" >> $LOG
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/api/hotels >> $LOG
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8002/api/hotels >> $LOG
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health >> $LOG
echo "" >> $LOG
