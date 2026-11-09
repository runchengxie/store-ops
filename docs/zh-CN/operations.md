# 运维与验证

[英文权威版本](../operations.md)

## 保留状态

数据目录、环境文件和凭据不进入 Git。源码迁移保留内容，不代替备份；使用备份前需检查。测试报告中不要发布原始店铺资料或凭据。

前端修改需在 `src/client` 执行 `npm run build`。后端修改需重启明确识别的本地服务，先核对 PID 和归属。Windows 停止辅助脚本会检查本安装目录的可执行文件/command，不因进程占用 8001 就停止它。

eMAG 计划准备页不注册任务。通用 Agent 调度器是另一执行路径，需要可用 Agent/model。本次审计没有启用新旧任务。

## 项目检查

在 `src/client`：

```bash
npm run typecheck
npm run test:i18n
npm run test:render
node scripts/check-errtext.mjs
npm run build
```

在 `src/server` 使用相应 Python 环境：

```bash
python -m pytest tests -q --timeout=120 --timeout-method=thread
python -m pytest app/tests -q --timeout=180 --timeout-method=thread
ruff check .
```

CI 将后端 suite 和平台矩阵分开，后端测试矩阵覆盖 Linux 和 Windows，macOS CI 暂时停用。安装 test/MCP test requirements，避免依赖缺失导致 skip。实际执行结果以审计表为准，不从 CI 配置推断成功。127.0.0.1:5199 的组件 harness 用合成 API 渲染真实 App，不可作为店铺证据。

当前仓库没有配置覆盖率阈值、专用安全扫描器或依赖审计 CI 门禁，不能描述为这些检查已通过。`uv pip check` 检查依赖兼容性，不查漏洞。`npm audit` 需要支持 audit endpoint 的 registry，镜像可能返回实现错误。

## 已知限制

- 回执发布前中止可能只留下旧记录，需核对时间和引用 ID。
- 平台时区、订单窗口、发票服务期间不能混用。
- 资料质量页展示后端 `stock_unknown` 汇总，包含缺失、格式异常和负数库存。
- Agent locale 不覆盖整个工作台，语言列表保存 ID 不使用 `en-US`。
- IvyeaAgent 是外部依赖，本次验证本仓库 adapter 与已安装版本，不代表验证每个上游版本和模型服务。
- 二进制包和 systemd 修改在部署前需要相应环境验证。

检查范围、实际结果及未执行项见[英文审计记录](../maintenance-audit.md)。

在仓库根目录运行 `python scripts/check-docs.py`，检查维护入口文档中的本地文件链接。该检查不验证外部网址或标题锚点。

[浏览器辅助 FBE 核对](browser-checks.md)
