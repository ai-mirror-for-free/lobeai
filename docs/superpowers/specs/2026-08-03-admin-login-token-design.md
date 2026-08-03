# 管理员登录接口 + 共享管理员会话 设计文档

日期：2026-08-03
状态：待评审

## 1. 背景与问题

new-api 新版鉴权在统一登录出口实施两级账户限制：

- `USER_SESSION_ACTIVE_LIMIT`（默认 50）：单用户未过期且 active 的 Session 上限，触顶新登录返回 `409 AUTH_SESSION_LIMIT`。
- `USER_SESSION_ISSUANCE_LIMIT`（默认 100）+ `USER_SESSION_ISSUANCE_WINDOW_SECONDS`（默认 86400）：统计窗口内该用户创建的所有 Session 上限（含已撤销），触顶返回 `429 AUTH_SESSION_ISSUANCE_LIMIT`。

现状：lobeai 的每个管理员接口（`generate-activation-codes` / `batch-create-tokens` / `openrouter/models` / `activation-codes/stats` / `usage-summary` / `price` / `text`）都通过 `get_admin_client`（`tools/VerifyAdmin.py`）使用请求体里的管理员账密，**每次调用登录一次 new-api、操作完成后登出**。虽然及时登出避免了活跃会话堆积，但：

1. 每次调用都计入签发窗口计数（100 次/天），外部对接方高频调用会触发 `AUTH_SESSION_ISSUANCE_LIMIT`。
2. 外部对接方需要持有管理员账密，每次调用都在请求体中透传账密，安全隐患大。
3. 会话签发窗口计数不因登出而清空，长期高频使用必然触顶。

## 2. 目标与约束

### 目标

1. 对外提供 `POST /api/admin/login`：对接方登录一次，换取 lobeai 本地签发的短期 token。
2. 后续管理接口调用改用 token 认证，不再每次透传管理员账密。
3. lobeai 内部使用**单一共享管理员会话**与 new-api 交互，new-api 上管理员账号活跃会话恒为 1、签发次数不随对接方调用增长。
4. 保留老对接方按账密直接调用管理接口的兼容路径。

### 已确认决策

- token 有效期：**24 小时**。
- 共享会话账密来源：现有环境变量 `NEWAPI_USER` + `NEWAPI_PASSWORD_ENCRYPTED`（管理员账号）。
- 老账密认证路径：**替换**为复用共享会话（不再每次临时登录→登出），账密改为本地比对配置的管理员账密。

### 非目标

- 不改 new-api、server_b、claude_agent 代码。
- 不改前端 claude_web。
- 不做多管理员体系（仍为单一管理员账号）。

## 3. 方案概览

```
对接方 A（老方式）                   对接方 B（新方式）
   │  POST /api/admin/usage-summary      │  POST /api/admin/login
   │  {username,password}                │  {username,password}
   │                                     │  → {token, expires_at}
   │                                     │
   │                                     │  POST /api/admin/usage-summary
   │                                     │  Authorization: Bearer <token>
   ▼                                     ▼
lobeai get_admin_client ──本地校验──→ SharedAdminSession（唯一）
                                             │  单个 requests.Session
                                             │  access_token 过期自动 refresh
                                             ▼
                                          new-api /api/...
```

核心改动：

| 文件 | 改动 |
|---|---|
| `main.py` | 新增 `POST /api/admin/login` 接口 |
| `tools/AdminTokenManager.py`（新增） | lobeai token 签发/校验/过期清理 |
| `tools/SharedAdminSession.py`（新增） | 全局共享管理员会话（单例 + 自动 refresh） |
| `services/NewAPIClient.py` | 新增 `refresh_login()` 方法 |
| `tools/VerifyAdmin.py` | 改造 `get_admin_client`：token / 账密两种认证，均返回共享会话 |
| `tools/RequestVaild.py` | 新增 `AdminLoginRequest`；`AdminAuthRequest` 增可选 `token: str = ""` |

## 4. 详细设计

### 4.1 `POST /api/admin/login`（新增）

```
POST /api/admin/login
Content-Type: application/json

{
  "username": "yang",
  "password": "******"
}
```

处理逻辑：

1. 本地校验账密：`username == NEWAPI_USER` 且 `password == 解密后的 NEWAPI_PASSWORD_ENCRYPTED`。解密失败/不匹配 → `401`。
   - 说明：管理员账号就是 lobeai 配置的管理员，本地比对即完成身份校验，**不向 new-api 发起登录**，因此不产生任何会话。
2. 校验通过 → `AdminTokenManager.issue_token(username)` 签发 token。
3. 返回：

```json
{
  "success": true,
  "data": {
    "token": "<urlsafe-random>",
    "token_type": "Bearer",
    "expires_at": 1754000000,
    "expires_in": 86400
  }
}
```

### 4.2 `AdminTokenManager`（新增，`tools/AdminTokenManager.py`）

- 内存 dict 存储：`{token: {"username": str, "expires_at": int}}`。
- `issue_token(username) -> str`：`secrets.token_urlsafe(32)` 生成，有效期 **24h**（模块常量 `TOKEN_TTL = 86400`）。
- `verify_token(token) -> dict|None`：查表 + 校验未过期；过期即删除并返回 None。
- `_cleanup()`：惰性清理——`verify_token` 时顺带清掉已过期 token，避免内存无限增长。
- 单进程内存存储即可：lobeai 以 `python main.py` 单进程运行（`run_server.sh`），无需跨进程共享。
- 登出语义：无独立 logout；token 24h 自动过期，进程重启后内存表清空（token 全部失效，对接方需重新 login）。

### 4.3 `NewAPIClient.refresh_login()`（新增，`services/NewAPIClient.py`）

现有 `login()` 登录后 session 保存了：

- `Authorization: Bearer <access_token>`（15 分钟过期）
- `new_api_refresh` cookie（HttpOnly，最长 30 天，登录时由 Set-Cookie 写入 session）

新增 `refresh_login() -> bool`：

1. `POST {base_url}/api/user/auth/refresh`（session 自动携带 refresh cookie）。
2. 成功：响应含新的 `access_token` + 轮换后的 refresh cookie（Set-Cookie 自动更新到 session）。用新 access_token 更新 `session.headers["Authorization"]`，返回 True。
3. 失败（401/网络错误）：返回 False，调用方 fallback 重新 `login()`。

### 4.4 `SharedAdminSession`（新增，`tools/SharedAdminSession.py`）

全局单例，管理一个长期有效的 `NewAPIClient`：

- 模块级持有 `_client` + `threading.Lock`。
- `get_admin_client() -> NewAPIClient`：
  1. `_client` 为空 → 加锁初始化并 `login()`（用 `NEWAPI_USER` + 解密密码）。
  2. 若上次访问距现在超过 12 分钟（access_token 15 分钟过期，留余量），加锁调 `refresh_login()`；失败则重新 `login()`。
  3. 返回 `_client`。
- 不提供 logout：共享会话生命周期与进程一致，登出会让所有后续调用失效。

### 4.5 `get_admin_client` 改造（`tools/VerifyAdmin.py`）

保留函数名与 Depends 用法（调用方 `main.py` 无需改动签名），认证逻辑改为二选一：

```
优先级 1（token 认证）：
  token 来源：Authorization: Bearer <token> 头，或请求体可选字段 token
  → AdminTokenManager.verify_token(token)
  → 通过：返回 SharedAdminSession.get_admin_client()
  → 失败：401

优先级 2（账密认证，兼容老对接方）：
  请求体 username/password
  → 本地比对 NEWAPI_USER + 解密密码
  → 通过：返回 SharedAdminSession.get_admin_client()
  → 失败：401
```

要点：

- 移除原 finally 中的 `logout()`——共享会话不能登出。
- 移除原逻辑中"向 new-api 登录验证 role==100"的步骤——身份校验改为本地账密比对，不再产生 new-api 会话。管理员角色信任基于配置（lobeai 配置的管理员即 new-api 管理员）。
- 依赖函数签名：`async def get_admin_client(creds: AdminAuthRequest, request: Request) -> AsyncIterator[NewAPIClient]`。
  - `creds: AdminAuthRequest`：从请求体解析（`AdminAuthRequest` 在原有 `username/password` 基础上**增加可选 `token: str = ""`**）。各具体接口的 Request 模型（`UsageSummaryRequest` 等）与它字段兼容——FastAPI 对依赖的 body 模型与端点的 body 模型做并集合并解析，多出的 `token` 字段在端点模型上被忽略，不影响现有接口。
  - `request: Request`：Starlette 原始请求，用于读取 `Authorization: Bearer <token>` 头。
  - `main.py` 中所有 `Depends(get_admin_client)` 用法不变。

### 4.6 main.py 管理接口改造

- 现有 admin 接口签名**不变**（仍 `admin_client: NewAPIClient = Depends(get_admin_client)`）。
- 因为 `get_admin_client` 现在返回共享会话，老接口自然获得"共享会话 + token/账密双认证"能力，无需逐接口改。
- 新增 login 接口独立于 get_admin_client（login 本身就是换取 token 的入口）。

### 4.7 错误处理

| 场景 | 行为 |
|---|---|
| login 账密不匹配 | `401 {"success": false, "message": "..."}` |
| token 无效/过期 | `401 {"success": false, "message": "token invalid or expired"}` |
| 未提供任何凭证 | `401` |
| 共享会话 refresh 失败后重登失败 | `500 {"success": false, "message": "admin session unavailable"}` |
| admin 操作内 new-api 接口失败 | 维持现状（各 service 各自捕获/抛 RuntimeError） |

## 5. 兼容性

- **老对接方**：继续传 `username/password`，走账密兼容路径（本地比对），无需改动。
- **新对接方**：`POST /api/admin/login` 拿 token → `Authorization: Bearer <token>` 调各 admin 接口。
- **new-api 侧**：管理员账号活跃会话从"随调用波动"变为恒为 1；签发次数从"每次调用 +1"变为"仅初始化时 1 次（及 refresh 失败重登的极少数情况）"。

## 6. 验证方式

无自动化测试框架（lobeai 无 pytest）。以 curl 手工验证为主：

1. `curl -X POST /api/admin/login -d '{"username":"...","password":"..."}'` → 返回 token。
2. `curl -X POST /api/admin/usage-summary -H "Authorization: Bearer <token>"` → 正常返回统计。
3. `curl -X POST /api/admin/usage-summary -d '{"username":"...","password":"..."}'` → 老账密路径正常。
4. 错误账密 / 伪造 token → 401。
5. new-api 侧确认：管理员账号 `user_sessions` 表中 active 会话数为 1，且连续调用不增长。

## 7. 风险与限制

1. **共享会话并发**：`requests.Session` 非严格线程安全。lobeai 为 FastAPI 单进程，多个请求可能同时触发 refresh。用 `threading.Lock` 串行化 refresh；`create_token` 这类"先建后取最新 id"的逻辑本身依赖 token 列表顺序，多对接方并发批量建 token 时可能互相干扰（现有逻辑在单会话下也被放大）。已确认场景为低频管理操作，接受此限制。
2. **token 存内存**：进程重启后全部失效，对接方需重新 login。属可接受（24h 有效期设计）。
3. **账密本地比对**：若 new-api 管理员密码变更，需同步更新 lobeai `.env` 的 `NEWAPI_PASSWORD_ENCRYPTED`；否则 login/账密认证都会失败。与现状一致（共享会话初始化同样依赖该密码）。
4. **无显式 logout**：token 24h 过期即视为登出；如需立即吊销，只能重启进程。
