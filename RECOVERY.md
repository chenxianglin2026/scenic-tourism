# 伊家智能科技 - 灾难恢复手册

## 如果电脑坏了/换了，找回全部内容只需 3 步：

### 1. 装回 Hermes Agent
```bash
curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/install.sh | bash
```

### 2. 恢复配置（以下内容复制到 ~/.hermes/config.yaml）
```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
  base_url: ''
providers:
  deepseek:
    api_key: 你的DeepSeek API Key
```

### 3. 克隆全部项目
```bash
mkdir -p ~/projects && cd ~/projects
git clone https://gitee.com/yjr2026/yijiaren-hotel.git yijiaren
git clone https://gitee.com/yjr2026/scenic-tourism.git scenic
git clone https://gitee.com/yjr2026/apartment-mgr.git apartment-mgmt
```

### 所有代码、文档、脚本已在 Gitee 永久保存：
- 巡检清单: scenic/CHECKLIST.md
- 团队分工: scenic/TEAM.md
- 系统架构: scenic/ARCHITECTURE.md
- 部署脚本: scenic/scripts/deploy-all.sh
- 冒烟测试: scenic/scripts/smoke_test.sh
- 健康检查: scenic/scripts/health_check.sh
- Nginx配置: scenic/nginx.conf
- 全部源代码: 三个Gitee仓库

### 服务器永久保存：
- deploy-all.sh (cron每5分钟)
- health_check.sh (cron每10分钟)
- 全部systemd服务配置

## 唯一需要手动备份的：
### DeepSeek API Key —— 记在安全地方
### SSH 密钥 —— 备份 ~/.ssh/id_ed25519
