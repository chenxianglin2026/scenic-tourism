# 经验教训库 (Lessons Learned)

> 目标：不重复踩坑。每次复杂问题解决后沉淀关键教训。

---

## 格式

```markdown
## [日期] 标题

**项目**: 伊家人 / KeepSafe / 景区
**Tier**: 操作风险等级
**问题**: 发生了什么
**根因**: 为什么发生
**解决**: 怎么解决的
**教训**: 以后怎么做
**关联**: 相关文件/commit
```

---

## 教训清单

### 2026-06-09 KeepSafe GitHub 大文件

**项目**: KeepSafe
**Tier**: Tier 2
**问题**: Push 被拒，仓库含 STL 65MB + OBJ 103MB
**根因**: 3D 建模文件被 git 追踪
**解决**: git filter-branch 清除历史 + .gitignore
**教训**: 创建仓库前检查大文件，大于 50MB 的文件加 .gitignore
**关联**: commit 547906b

### 2026-06-09 伊家人 E2E 测试端口

**项目**: 伊家人
**Tier**: Tier 1
**问题**: e2e_full_test.py 端口配置错误 (8000 vs 8001)
**根因**: 后端端口 8000 是内部 uvicorn，nginx 对外是 8001
**解决**: 修改测试端口为 8001，修复响应解包逻辑
**教训**: 测试端口必须与实际运行端口一致，e2e 测试用外部端口

### 2026-06-08 KeepSafe MQTT 静默 bug

**项目**: KeepSafe
**Tier**: Tier 1
**问题**: MQTT 所有消息处理静默失败，日志中零活动
**根因**: _on_message 是同步回调，调用了 async handler 但没有 await
**解决**: 改为 asyncio.get_running_loop().create_task()
**教训**: Python async/sync 混用是陷阱，所有 MQTT 回调必须显式调度

### 2026-06-08 伊家人 小程序 API 不匹配

**项目**: 伊家人
**Tier**: Tier 2
**问题**: 小程序登录接口与后端完全不匹配 (端点名、参数名、响应格式)
**根因**: 前后端分开开发，缺少 API 契约约束
**解决**: 逐一修正 api.js、app.js、login.js 中的端点/参数/响应处理
**教训**: 新项目先定义 API 契约文档，前后端对齐后再开发
