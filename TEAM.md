# AI 编码团队分工与流程 v2.0

## 角色
| 角色 | 工具 | 职责 |
|------|------|------|
| 陈总 | — | 提需求、测验收、定方向 |
| Kimi | kimi CLI | 编码（kimi -p "..."） |
| Hermes | 本Agent | 审计+调度+部署+验证 |

## 铁律
1. Hermes 不写代码 → 只审
2. Kimi 出码 → Hermes 审 → git push → cron部署
3. 陈总不充当 relay → 代码审核自动走

## 工作流
1. 陈总提需求
2. Hermes 拆解 → 写 Kimi 任务文件（/tmp/kx.txt）
3. Hermes 调用: kimi -p "$(cat /tmp/kx.txt)"
4. Kimi 完成 → Hermes git diff 审计
5. 审计通过 → git push Gitee
6. 服务器 cron auto deploy
7. Hermes 验证（curl + 页面）

## 审计标准（5项）
1. py_compile 编译通过
2. API 前缀正确（景区/scenic/api/ 非 /api/）
3. 硬编码清零（grep admin123）
4. JS 括号平衡
5. 不删已有功能
