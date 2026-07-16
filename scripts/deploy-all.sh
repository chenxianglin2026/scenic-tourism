#!/bin/bash
LOG=/tmp/deploy-all.log
echo "$(date): Starting auto-deploy" >> $LOG

cd /home/ubuntu/apartment/code/backend 2>/dev/null && cd /home/ubuntu/apartment/code 2>/dev/null && {
    git pull https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/apartment-mgr.git main >> $LOG 2>&1
    if [ "$(git diff HEAD@{1} --name-only 2>/dev/null | wc -l)" != "0" ]; then
        sudo find /home/ubuntu/apartment/code -name "__pycache__" -exec rm -rf {} + 2>/dev/null
        sudo systemctl restart apartment 2>/dev/null
        echo "$(date): Apartment restarted" >> $LOG
    fi
}

cd /home/ubuntu/yijiaren/code 2>/dev/null && {
    sudo git pull "https://yjr2026:20a43a07393286689a5260d93a3ae081@gitee.com/yjr2026/yijiaren-hotel.git" main >> $LOG 2>&1
    # 同步backend (套娃路径: code/code/backend/)
    sudo mkdir -p /home/ubuntu/projects/yijiaren/app/api 2>/dev/null
    sudo cp /home/ubuntu/yijiaren/code/code/backend/app/api/*.py /home/ubuntu/projects/yijiaren/app/api/ 2>/dev/null
    sudo cp /home/ubuntu/yijiaren/code/code/backend/app/main.py /home/ubuntu/projects/yijiaren/app/main.py 2>/dev/null
    sudo find /home/ubuntu/projects/yijiaren -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    sudo systemctl restart yijiaren 2>/dev/null
    echo "$(date): Hotel synced" >> $LOG
}


