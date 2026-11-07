# 配置

可选价格执行在服务器启动时读取 `IVYEA_OPS_EMAG_WRITES_ENABLED`（默认 `0`）和 `IVYEA_OPS_EMAG_WRITE_STORE_ID`（默认空），两项必须明确允许指定店铺。见[价格API](emag-write-readiness.md)。配置不会让现有本地审批或MCP令牌获得平台提交权限。

[英文权威版本](../configuration.md)

## 配置来源

参考模板位于 [`configs/server.env.example`](../../configs/server.env.example)。新建安装时，源码版将其复制到 `src/server/.env`，冻结发行包复制到 `server/.env`。填写必要的值，并保留已有配置。

`src/server/app/core/config.py` 在启动时读取环境变量。源码使用 `src/server/.env`，缺失时兼容旧 `server/.env`；冻结包使用 `server/.env`。`IVYEA_OPS_ROOT` 可显式指定运行环境 root。已有进程环境值优先于 dotenv。

标准运行依赖包含 HTTP 的 SOCKS 代理支持。

可运行时修改的设置在数据目录的 `hub_settings.json`，通过应用系统设置管理。回退由各集成决定，不保证所有空值都有环境回退。实际键由 `src/server/app/core/hub_settings.py` 和消费方定义。

| key | 默认或含义 |
|---|---|
| `IVYEA_OPS_HOST` | `127.0.0.1` |
| `IVYEA_OPS_PORT` | `8001` |
| `IVYEA_OPS_DEV` | `0`，development 的 CORS/cookie 行为不同 |
| `IVYEA_OPS_SECRET` | 缺失时临时生成，需要固定值以保持会话 |
| `IVYEA_OPS_USER` | `admin` |
| `IVYEA_OPS_PASSWORD_HASH` | bcrypt password hash |
| `ADMIN_PASSWORD` | 未配置 hash 时的启动明文替代值，会转为 hash |
| `IVYEA_OPS_ALLOWED_ORIGINS` | 允许进行浏览器写请求的 origin，逗号分隔 |
| `IVYEA_OPS_COOKIE_DOMAIN` | 空，host-only cookie |
| `IVYEA_OPS_DATA_DIR` | `<runtime-root>/data` |

在本机环境文件中设置 `IVYEA_OPS_DATA_DIR=~/data/ivyeaops/runtime`，可将运行数据放到仓库外。`~` 会展开为当前用户的主目录。复制现有数据前请停止服务并备份；修改配置本身不会迁移文件。CLI 和服务进程必须使用相同的值，进程环境变量优先于环境文件。其他工具和本地脚本可能使用独立路径。

使用 `~` 时，服务和 CLI 也必须以同一用户账号运行。本地日志和诊断输出仍可能包含绝对路径，移动数据目录不会清除已有记录。如果旧数据中有 `.master.key`，应将它与加密配置一同保留。

本机浏览器应配置实际 origin，例如 `http://127.0.0.1:8001`，反向代理使用相应 HTTPS origin。development 模式改变安全行为，不能作为生产捷径。

## eMAG 凭据与运行模式

联网 CLI 读取 Windows Generic Credential `IvyeaOps/eMAG/RO`。浏览器保存网站密码与此不同。target 不是环境键或公开 API 字段，网页不读取密码。平台 API 权限和 IP 白名单仍须有效。

`--days` 为 1–29 的整数，默认 29。`--from-latest` 只读取已有快照，不联网、不读取凭据。其他平台可导入和重放，目前保存凭据的联网入口限 Windows。

标准应用仍有会话认证和管理员检查。私有本地开发适配器不属于发布的认证契约。

## 模型、集成与 locale

console 和图片翻译需要相应模型服务。RO/BG/HU 是图片翻译目标语言，不表示另接入了这些国家的店铺。确定性采集、离线巡检和本地草稿不需要模型。

仅启用 eMAG 电商 adapter。Amazon 数据源默认项及自动注册已移除，既有私有值保留。通用外部 Agent 仍是独立集成，安装 skill 不授予平台权限。GBrain 已不是知识库运行环境，不应使用旧 GBrain 配置示例。

只有 Agent 子界面有 i18next。英语资源的稳定 ID 为 `en`，不是 `en-US`；保存偏好默认 `zh-CN`，缺失翻译回退 `en`，不支持的保存值回到默认。主工作台没有全局 locale。语言只改变界面显示，不改变 API key、schema、ID、证据或计算。
