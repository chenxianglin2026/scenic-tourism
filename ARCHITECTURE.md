# 伊家智能科技 - 系统架构 v2.0

## 服务器: 腾讯云上海 111.229.30.253

## 三系统

| 系统 | 端口 | git目录 | 服务目录 | nginx读取 |
|------|:--:|------|------|------|
| 酒店 | 8001 | /home/ubuntu/yijiaren/code/ | gitee直读 | alias git |
| 景区 | 8002 | /home/ubuntu/projects/scenic/code/ | gitee直读 | alias git |
| 公寓 | 8000 | /home/ubuntu/apartment/code/ | gitee直读 | proxy |

## nginx 规则 (已入Gitee版本库)
- `/admin/` → alias git目录 (酒店)
- `/scenic/admin/` → alias git目录 (景区) 
- `/api/` → proxy 8001 (酒店)
- `/scenic/api/` → proxy 8002 (景区)
- `/apartment/` → proxy 8000 (公寓)

## 部署: deploy-all.sh (cron每5分钟)
git pull → 无cp → systemctl restart → curl验证

## Gitee 仓库
- 酒店: yjr2026/yijiaren-hotel
- 景区: yjr2026/scenic-tourism
- 公寓: yjr2026/apartment-mgr

## 备案
- 主站: 粤ICP备16027093号-2
- VIP: 粤ICP备16027093号
