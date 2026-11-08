# Go 任务管家

[English](../go-supervisor.md)

可选任务管家只安排固定的 eMAG 只读巡检。Go 管派发和持久任务状态；Python 保留采集、凭证、快照发布、业务检查和权威暂停控制；TypeScript 页面不变。

## 构建与配置

在 `src/supervisor` 使用模块和 CI 指定的 Go 版本：

```bash
go test -race ./...
go vet ./...
go build -o /private/release/store-ops-supervisor ./cmd/store-ops-supervisor
```

参照 `configs/supervisor.example.json`，实际配置保存在私有配置根目录。`python`、`server_dir` 和 `data_dir` 必须使用绝对路径。这里的 `data_dir` 保存管家自身状态，与 Python 运行数据根目录不同。Python 从稳定发布目录下的服务端目录运行，沿用原有设置和凭证。安装的服务不能指向临时 worktree，配置中不放凭证。当前真实采集只使用一个 Windows 凭证目标，私有启动器必须设置 `IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID`，明确对应的店铺标识。缺失或不匹配会在采集前拒绝执行。多个任务槽位暂不代表支持多个真实凭证账户。

```bash
store-ops-supervisor run --config /private/config/supervisor.json
store-ops-supervisor status --config /private/config/supervisor.json
```

安装后首次派发在配置的间隔后发生，不立即采集。休眠期间错过的周期合并，不积压补跑。默认并发为二，同一店铺串行。网络等待不要求把现有 Python 分析全部重写成 Go。

## 恢复与暂停

管家先保存任务意图，再启动固定的 `app.supervisor_bridge`；不接受任意 shell 命令或平台写操作。桥接将任务标识与原有 Python 巡检回执关联，同一个任务不重复执行。

`status` 命令读取持久任务状态；进程是否存活需另外检查操作系统服务或计划任务。原有店铺暂停状态仍是权威来源。暂停的排队任务最多每 30 秒复查一次。暂停后不再派发，运行中的 Python 在现有请求或发布检查点协作停止。超时请求只取消对应任务，不暂停整个店铺。发出取消请求不等于已经停止，不使用广泛杀进程。

管家崩溃后，未完成任务需核对回执。身份匹配的最终回执可确定结果；缺失或未知结果会阻止同店铺再次运行，需所有者核查。不要删除运行中或未知记录来强制重试。状态或配置异常时拒绝继续派发。处理未知状态前应核对实际进程、回执身份和原有店铺锁。

它提供周期性只读监控，并不保证永不中断：笔记本休眠、注销、断网或平台故障仍影响新鲜度。Python 应用及其 Agent 调度器不被替换。

## Windows 切换与回退

使用能够访问原有凭证的交互式 Windows 用户身份。备份原每日任务 XML、程序、配置和状态，确认没有采集正在运行。管家安装到稳定目录，保留服务端任务和手动采集任务。先禁用被替换的每日触发器，再启用新管家，不能让两个自动调度器同时管理同一店铺。

验证启动、真实关联回执、暂停和重启恢复后，才视为迁移完成。失败时只停止已确认的管家，确认没有工作进程仍在运行，再恢复备份的每日任务。不能为部署重置凭证、环境密钥或密码哈希。实际机器路径、任务名称及验证回执只保留在私有记录。

## 语言选择

全部改成 Go 技术上可行，但需替换并重新验证 API、表格、分析和知识库代码，本阶段保留已测试的 Python 部分。Rust 的编译期所有权和内存安全适合资源控制重要的场景，这里会增加开发复杂度。C/C++ 的底层控制暂时没有已证实的需求。C#/.NET 同样可行，尤其适合 Windows，也支持单文件发布。选择 Go 是为了这层小型跨平台任务管理，并非其他语言不能长期运行。

参考：[Go 并发](https://go.dev/doc/effective_go#concurrency)、[Rust 所有权](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html)、[.NET 单文件发布](https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview)。
