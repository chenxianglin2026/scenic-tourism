# 三项目治理体系 (Three-Project Governance System)

> 版本: v1.0 | 创建: 2026-06-09 | 负责人: Hermes (AI 开发总监)
> 
> 核心目标：不是让 AI 多写代码，而是构建 "人-AI-知识库" 的闭环治理体系。

---

## 一、体系架构

```
~/projects/
├── GOVERNANCE.md          ← 本文：治理总纲
├── BOUNDARIES.md          ← 项目边界：可改/不可改
├── RISK-TIERS.md          ← 风险分级：Tier 0-3
├── ARCHITECTURE.md        ← 三项目整体架构
├── lessons/               ← 经验沉淀
│   ├── LESSONS.md         ← 通用教训
│   └── YYYY-MM-DD.md      ← 按日记录
├── daily/                 ← 每日复盘
│   ├── TEMPLATE.md        ← 复盘模板
│   └── YYYY-MM-DD.md      ← 每日复盘记录
├── weekly/                ← 周度优化
│   └── YYYY-WW.md
├── monthly/               ← 月度检视
│   └── YYYY-MM.md
├── yijiaren/
│   ├── ARCHITECTURE.md    ← 伊家人架构
│   └── lessons/
├── keepsafe/
│   ├── ARCHITECTURE.md    ← KeepSafe架构
│   └── lessons/
└── scenic/
    ├── ARCHITECTURE.md    ← 景区架构
    └── lessons/
```

---

## 二、治理原则

### 2.1 边界先行
- 任何操作前先确认：这是哪个项目？哪个环境？Tier 几？
- 生产环境（VPS 运行中的容器、微信已发布的小程序）→ Tier 3，需人工审批
- 本地代码 → Tier 0-1，AI 自主执行

### 2.2 风险预判
- AI 执行任何操作前，必须自问：影响范围多大？回滚方案是什么？
- Tier 2+ 操作必须报告中说明风险 + 回滚方案

### 2.3 知识沉淀
- 每次复杂问题解决后 → 沉淀到 lessons/
- 架构变更 → 更新 ARCHITECTURE.md
- 不重复踩坑

### 2.4 每日复盘
- 每天结束前：记录 AI 失误点、协作卡点
- 每周：优化 workflow
- 每月：检视知识体系进化

---

## 三、项目速查

| 项目 | 代码路径 | GitHub | VPS | 状态 |
|------|---------|--------|-----|------|
| 伊家人 | ~/projects/yijiaren/code | chenxianglin2026/-yijiaren-hotel | :80→8001(yijiaren-app) | 小程序待审核 |
| KeepSafe | ~/projects/keepsafe | chenxianglin2026/keepsafe-tracker | :8000 | SIM待激活 |
| 景区 | ~/projects/scenic/code | chenxianglin2026/scenic-tourism | :8002(scenic-backend) | AppID待注册 |

VPS: 43.163.5.90 (TencentOS, Docker)
HTTPS: 443 (宿主机nginx, 自签证书)

---

## 四、工作流

```
用户指令 → AI 判断 Tier → 
  Tier 0-1: 直接执行 → commit → push
  Tier 2: 报告中注明风险 → 执行 → 验证
  Tier 3: 报告风险 + 回滚方案 → 等待确认 → 执行
```

### 陈总铁律 (v4)
1. Hermes = 总监，全权分配/审查/交付，不请示不hands-on
2. 沟通不影响团队干活
3. 发挥专业能力（OpenClaw 独立任务）
4. 独立审查员把关代码质量
5. 三项目并行
6. 汇报 bullet points 只给结论

---

## 五、关键约定

- Python 关键字: `lat`/`lng`/`enabled` (非 latitude/longitude/enable)
- 公众号充电桩菜单原封不动
- 3D 建模交豆包处理
- ESP32 烧录用 USB-OTG 口
- 微信小程序上传用 miniprogram-ci
- commit 格式: type: 描述 (feat/fix/test/refactor/docs/chore)
