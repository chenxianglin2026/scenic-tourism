# AGENTS.md - Scenic Smart Tourism

## Tech Stack
- 后端: Python FastAPI + SQLite, 71 API 端点
- 前端: 微信小程序 (6 页) + 管理后台 (11 页 HTML/CSS/JS)
- 部署: Docker Compose, VPS 43.163.5.90:8002
- OTA: 携程/美团/飞猪对接框架 (810 行)
- 主题色: #c8a052 (金色)

## Rules
- Python 关键字: lat/lng/enabled
- 管理后台 root = /app/admin
- 测试: 170 tests, 目标全绿
- commit 格式: type: 描述 (feat/fix/test/refactor/docs/chore)
- 开发自主推进, 不需请示

## Style
- 金色主题 (#c8a052)
- 中文字体 PingFang SC / Microsoft YaHei
- 汇报: bullet points, 只用结果

## Governance (三项目治理体系)

**必读文档** (每次操作前判定):
- `docs/GOVERNANCE.md` — 治理总纲
- `docs/BOUNDARIES.md` — 可改/不可改区域
- `docs/RISK-TIERS.md` — 风险分级 Tier0-3

**执行规则**:
- Tier0-1: 自主执行
- Tier2: 报告中注明风险+回滚方案
- Tier3: 向陈总报告→等待确认→执行

**当天结束后写入**: `docs/LESSONS.md` (经验)
**每日复盘模板**: `~/projects/daily/TEMPLATE.md`

## Red Lines
- Don't exfiltrate private data.
- Don't run destructive commands without asking.
- `trash` > `rm`
