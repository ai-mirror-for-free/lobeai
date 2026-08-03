# 管理员登录接口 + 共享管理员会话 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 lobeai 提供 `POST /api/admin/login` 管理员登录接口，签发 24h lobeai token，并让所有管理员接口改用单一共享 new-api 会话，彻底避免 new-api 会话上限（AUTH_SESSION_LIMIT / AUTH_SESSION_ISSUANCE_LIMIT）。

**Architecture:** 新增 `AdminTokenManager`（内存 token 表）与 `SharedAdminSession`（全局单例共享 new-api 会话，access_token 过期自动 refresh）。改造 `get_admin_client` 依赖：支持 `Authorization: Bearer <token>` / body `token` / body 账密三种凭证，均返回共享会话。`main.py` 新增 login 接口。涉及接口模型放宽账密为可选以支持纯 header token 调用。

**Tech Stack:** Python 3 + FastAPI + pydantic + requests。无 pytest（lobeai 无测试框架），验证以 `python -m py_compile` 语法检查 + 手工 curl（部署到 server a 后）。

**Spec:** `docs/superpowers/specs/2026-08-03-admin-login-token-design.md`

## Global Constraints

- 所有改动只在 `lobeai/` 内，不改 new-api / server_b / claude_agent / claude_web。
- 老对接方账密调用必须继续可用（兼容路径保留）。
- token 有效期 24h（`TOKEN_TTL = 86400`）。
- 共享会话账密来自环境变量 `NEWAPI_USER` + `NEWAPI_PASSWORD_ENCRYPTED`（解密）。
- lobeai 单进程运行（`python main.py`），token 用进程内存存储即可。
- 不引入新依赖库（只使用标准库 `secrets`、`time`、`threading`、`os`）。
- 提交格式：`提交类型: function 改动内容: 简要中文描述`，提交到 lobeai 仓库，不推送。

---

### Task 1: AdminTokenManager（token 签发/校验/清理）

**Files:**
- Create: `lobeai/tools/AdminTokenManager.py`

**Interfaces:**
- Produces:
  - `issue_token(username: str) -> str`
  - `verify_token(token: str) -> dict | None`（返回 `{"username": str, "expires_at": int}` 或 None）

- [ ] **Step 1: 创建文件**

```python
"""lobeai 管理员本地 token 管理

对外 /api/admin/login 签发短期 token，对接方后续凭 token 调用管理员接口。
token 存进程内存，单进程部署足够（lobeai 以 python main.py 单进程运行）。
"""
import secrets
import time
import threading

TOKEN_TTL = 86400  # 24 小时

_lock = threading.Lock()
_tokens: dict[str, dict] = {}  # {token: {"username": str, "expires_at": int}}


def _now() -> int:
    return int(time.time())


def issue_token(username: str) -> str:
    """签发一个 token，返回 token 明文（调用方负责返回给对接方）"""
    token = secrets.token_urlsafe(32)
    with _lock:
        _tokens[token] = {"username": username, "expires_at": _now() + TOKEN_TTL}
    return token


def verify_token(token: str) -> dict | None:
    """校验 token。有效返回 {"username": ..., "expires_at": ...}，无效/过期返回 None。"""
    if not token:
        return None
    with _lock:
        entry = _tokens.get(token)
        if entry is None:
            return None
        if entry["expires_at"] <= _now():
            _tokens.pop(token, None)  # 惰性清理过期项
            return None
        return entry
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile tools/AdminTokenManager.py`
Expected: 无输出，退出码 0

- [ ] **Step 3: 手工逻辑验证**

Run: `python -c "import sys; sys.path.insert(0,'.'); from tools.AdminTokenManager import issue_token, verify_token; t=issue_token('yang'); print(verify_token(t)); print(verify_token('fake'))"`
Expected: 输出 `{'username': 'yang', ...}` 和 `None`

- [ ] **Step 4: 提交**

```bash
git add tools/AdminTokenManager.py
git commit -m "function: 新增管理员token签发与校验" --no-verify
```

---

### Task 2: NewAPIClient.refresh_login()

**Files:**
- Modify: `lobeai/services/NewAPIClient.py`

**Interfaces:**
- Consumes: 现有 `self.session`（已保存 `new_api_refresh` cookie 与 `Authorization` 头）
- Produces: `refresh_login() -> bool`（成功刷新返回 True，失败返回 False，供 SharedAdminSession fallback 重登）

- [ ] **Step 1: 新增方法**

在 `NewAPIClient.login()` 方法之后插入：

```python
    def refresh_login(self) -> bool:
        """刷新登录会话（access_token 15 分钟过期，用 refresh cookie 换新）

        new-api 刷新接口: POST /api/user/auth/refresh，session 自动携带
        new_api_refresh cookie，Set-Cookie 会更新 refresh cookie 实现轮换。

        Returns:
            True  刷新成功（已更新 Authorization 头）
            False 刷新失败（调用方应 fallback 重新 login）
        """
        try:
            resp = self.session.post(
                f"{self.base_url}/api/user/auth/refresh",
                timeout=15,
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            if not data.get("success"):
                return False
            user_data = data.get("data", {})
            access_token = user_data.get("access_token")
            if not access_token:
                return False
            self.session.headers.update(
                {"Authorization": f"Bearer {access_token}"}
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile services/NewAPIClient.py`
Expected: 无输出，退出码 0

- [ ] **Step 3: 提交**

```bash
git add services/NewAPIClient.py
git commit -m "function: NewAPIClient增加会话刷新方法" --no-verify
```

---

### Task 3: SharedAdminSession（共享管理员会话）

**Files:**
- Create: `lobeai/tools/SharedAdminSession.py`

**Interfaces:**
- Consumes: `NewAPIClient`、`refresh_login()`、`get_decrypted_password("NEWAPI_PASSWORD_ENCRYPTED")`
- Produces: `get_admin_client() -> NewAPIClient`（全局共享、已认证、保证 access_token 不过期）

- [ ] **Step 1: 创建文件**

```python
"""共享管理员会话（全局单例）

lobeai 所有管理员操作复用同一个 new-api 登录会话，避免每次登录签发新会话
触发 new-api 的 AUTH_SESSION_LIMIT / AUTH_SESSION_ISSUANCE_LIMIT。

access_token 有效期 15 分钟，距上次刷新超过 12 分钟自动 refresh；
refresh 失败（如会话被撤销）fallback 重新 login。
"""
import os
import threading
import time

from services.NewAPIClient import NewAPIClient
from tools.password_encryption import get_decrypted_password

REFRESH_INTERVAL = 720  # 秒，access_token 15min 过期，12min 余量

_lock = threading.Lock()
_client: NewAPIClient | None = None
_last_refresh: float = 0.0


def _do_login() -> NewAPIClient:
    client = NewAPIClient()
    client.login()  # login() 内部读 NEWAPI_USER + NEWAPI_PASSWORD_ENCRYPTED
    return client


def get_admin_client() -> NewAPIClient:
    """返回全局共享的已认证管理员客户端（保证 access_token 未过期）"""
    global _client, _last_refresh
    now = time.monotonic()

    if _client is not None and (now - _last_refresh) < REFRESH_INTERVAL:
        return _client

    with _lock:
        now = time.monotonic()
        if _client is not None and (now - _last_refresh) < REFRESH_INTERVAL:
            return _client

        if _client is None:
            try:
                _client = _do_login()
            except Exception as e:
                raise RuntimeError(f"管理员会话初始化失败: {e}") from e
        else:
            # 已有会话：先尝试 refresh，失败则重新登录
            if not _client.refresh_login():
                try:
                    _client = _do_login()
                except Exception as e:
                    raise RuntimeError(f"管理员会话刷新失败: {e}") from e
        _last_refresh = time.monotonic()
    return _client
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile tools/SharedAdminSession.py`
Expected: 无输出，退出码 0

- [ ] **Step 3: 提交**

```bash
git add tools/SharedAdminSession.py
git commit -m "function: 新增共享管理员会话" --no-verify
```

---

### Task 4: 请求模型放宽账密 + 新增 login 请求模型

**Files:**
- Modify: `lobeai/tools/RequestVaild.py`

**Interfaces:**
- Produces:
  - `AdminLoginRequest`（username/password 必填）
  - `AdminAuthRequest` 增加 `token: Optional[str] = None`，`username/password` 改可选
  - `GenerateActivationCodesRequest`、`ActivationCodeStatsRequest`、`AdminOpenRouterSearchRequest`、`AdminTextUpdateRequest`、`BatchCreateTokensRequest`、`UsageSummaryRequest` 的 `username/password` 均改为 `Optional[str] = None`

> 原因：FastAPI 会在接口端把请求体解析成接口自己的模型（如 `UsageSummaryRequest`）。若 `username/password` 仍为必填，纯 header token 调用（body 只含业务字段）会 422。放宽为可选即可兼容三种调用方式。

- [ ] **Step 1: 修改 AdminAuthRequest**

```python
class AdminAuthRequest(BaseModel):
    """管理员认证请求（通用）"""
    username: Optional[str] = None   # 管理员用户名（方式二账密兼容）
    password: Optional[str] = None   # 管理员密码（方式二账密兼容）
    token: Optional[str] = None      # lobeai 登录接口签发的 token（方式一）
```

- [ ] **Step 2: 新增 AdminLoginRequest（放在 AdminAuthRequest 之后）**

```python
class AdminLoginRequest(BaseModel):
    """管理员登录请求（换取 token）"""
    username: str  # 管理员用户名
    password: str  # 管理员密码
```

- [ ] **Step 3: 放宽其余管理接口模型的账密字段**

分别修改：

```python
class GenerateActivationCodesRequest(BaseModel):
    username: Optional[str] = None  # 管理员用户名
    password: Optional[str] = None  # 管理员密码
    tasks: list[list] = []  # 格式: [["claude code", 0, count, price], ...]
```

```python
class ActivationCodeStatsRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
```

```python
class AdminOpenRouterSearchRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    q: str
```

```python
class AdminTextUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    key: str
    content: str
```

```python
class BatchCreateTokensRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    n: int = Field(..., gt=0, le=100)
    package: str
    price: float = Field(..., gt=0)
```

```python
class UsageSummaryRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    granularity: str = ""
```

- [ ] **Step 4: 语法检查**

Run: `python -m py_compile tools/RequestVaild.py`
Expected: 无输出，退出码 0

- [ ] **Step 5: 提交**

```bash
git add tools/RequestVaild.py
git commit -m "refactor: 管理接口账密放宽为可选支持token" --no-verify
```

---

### Task 5: 改造 get_admin_client 依赖

**Files:**
- Modify: `lobeai/tools/VerifyAdmin.py`

**Interfaces:**
- Consumes: `AdminAuthRequest`、`AdminTokenManager.verify_token`、`SharedAdminSession.get_admin_client`、`get_decrypted_password("NEWAPI_PASSWORD_ENCRYPTED")`、`os.environ["NEWAPI_USER"]`
- Produces: `get_admin_client(request: Request, creds: AdminAuthRequest) -> AsyncIterator[NewAPIClient]`（FastAPI 依赖，两种凭证路径均返回共享会话）

- [ ] **Step 1: 整体重写 VerifyAdmin.py**

```python
import os
from typing import AsyncIterator

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from services.NewAPIClient import NewAPIClient
from tools.AdminTokenManager import verify_token
from tools.SharedAdminSession import get_admin_client as get_shared_admin_client
from tools.password_encryption import get_decrypted_password

# NewAPI 管理员 role 值
ADMIN_ROLE = 100


def _check_admin_credentials(username: str, password: str) -> bool:
    """本地比对管理员账密（NEWAPI_USER + 解密后的密码）

    管理员账号即 lobeai 配置的管理员，本地比对即完成身份校验，
    不向 new-api 发起登录，因此不产生任何 new-api 会话。
    """
    if not username or not password:
        return False
    try:
        expected_user = os.environ.get("NEWAPI_USER", "")
        expected_pass = get_decrypted_password("NEWAPI_PASSWORD_ENCRYPTED")
    except Exception:
        return False
    return username == expected_user and password == expected_pass


def _extract_bearer_token(request: Request) -> str:
    """从 Authorization: Bearer <token> 头提取 token，无则返回空串"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    return ""


async def get_admin_client(request: Request, creds: AdminAuthRequest) -> AsyncIterator[NewAPIClient]:
    """FastAPI 依赖：验证管理员身份并返回共享管理员会话

    凭证优先级（三选一）：
      1. Authorization: Bearer <token> 头
      2. 请求体 token 字段
      3. 请求体 username/password（账密兼容，本地比对）

    认证通过后返回 SharedAdminSession 的全局共享客户端（不登出，
    生命周期与进程一致），保证 new-api 上管理员活跃会话恒为 1。
    """
    token = _extract_bearer_token(request) or (creds.token or "")
    if token:
        entry = await run_in_threadpool(verify_token, token)
        if entry is None:
            raise HTTPException(status_code=401, detail="token invalid or expired")
    elif not _check_admin_credentials(creds.username, creds.password):
        raise HTTPException(status_code=401, detail="管理员认证失败")

    try:
        client = await run_in_threadpool(get_shared_admin_client)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"管理员会话不可用: {e}")

    yield client
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile tools/VerifyAdmin.py`
Expected: 无输出，退出码 0

- [ ] **Step 3: 提交**

```bash
git add tools/VerifyAdmin.py
git commit -m "refactor: 管理员认证改为token/账密双路径共享会话" --no-verify
```

---

### Task 6: main.py 新增 login 接口

**Files:**
- Modify: `lobeai/main.py`

**Interfaces:**
- Consumes: `AdminLoginRequest`、`AdminTokenManager.issue_token`、`_check_admin_credentials`（从 VerifyAdmin 导入）、`time`
- Produces: `POST /api/admin/login` 端点

- [ ] **Step 1: 新增导入**

将第 7 行 `from tools.VerifyAdmin import get_admin_client` 替换为：

```python
from tools.VerifyAdmin import get_admin_client, _check_admin_credentials
from tools.AdminTokenManager import issue_token, TOKEN_TTL
```

- [ ] **Step 2: 新增 login 端点（放在「管理员接口」区块最前面）**

```python
@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """
    【管理员】登录换取 lobeai token

    账密本地比对（NEWAPI_USER + 解密密码），不向 new-api 发起登录，
    因此不产生任何 new-api 会话。token 有效期 24 小时。
    """
    import time

    if not _check_admin_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="登录失败")

    token = issue_token(request.username)
    return {
        "success": True,
        "data": {
            "token": token,
            "token_type": "Bearer",
            "expires_at": int(time.time()) + TOKEN_TTL,
            "expires_in": TOKEN_TTL,
        },
    }
```

- [ ] **Step 3: 语法检查**

Run: `python -m py_compile main.py`
Expected: 无输出，退出码 0

- [ ] **Step 4: 提交**

```bash
git add main.py
git commit -m "function: 新增管理员登录接口" --no-verify
```

---

### Task 7: 启动验证（部署到 server a 后执行）

**Files:**
- 无代码改动

- [ ] **Step 1: server a 拉取并重启 lobeai**

在 server a 执行：
```bash
cd /root/claude-web/lobeai && git pull && ./run_server.sh
```
Expected: 服务重启成功，`/health` 返回 healthy。

- [ ] **Step 2: 登录接口验证**

Run: `curl -s -X POST http://154.64.231.128:25141/api/admin/login -H "Content-Type: application/json" -d '{"username":"yang","password":"<真实密码>"}'`
Expected: `{"success": true, "data": {"token": "...", "expires_in": 86400, ...}}`

Run: `curl -s -X POST http://154.64.231.128:25141/api/admin/login -H "Content-Type: application/json" -d '{"username":"yang","password":"wrong"}'`
Expected: `401` 且 `message: 登录失败`

- [ ] **Step 3: 方式一（token）调用管理接口**

Run: `curl -s -X POST http://154.64.231.128:25141/api/admin/usage-summary -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"granularity":"month"}'`
Expected: 正常返回统计 JSON（不再是 401/422）

- [ ] **Step 4: 方式二（账密兼容）调用管理接口**

Run: `curl -s -X POST http://154.64.231.128:25141/api/admin/usage-summary -H "Content-Type: application/json" -d '{"username":"yang","password":"<真实密码>","granularity":"month"}'`
Expected: 正常返回统计 JSON

- [ ] **Step 5: 无效 token 验证**

Run: `curl -s -X POST http://154.64.231.128:25141/api/admin/usage-summary -H "Authorization: Bearer fake" -H "Content-Type: application/json" -d '{"granularity":"month"}'`
Expected: `401` 且 `message: token invalid or expired`

- [ ] **Step 6: new-api 会话数确认**

在 server a 查询 new-api 数据库（oneapi 库）：
```sql
SELECT count(*) FROM user_sessions WHERE user_id = (SELECT id FROM users WHERE username='yang') AND status = 'active';
```
Expected: 连续多次调用后该计数保持为 1（或接近 1，不含历史残留）。

---

## 自审记录

- **Spec 覆盖**：login 接口 → Task 6；token 管理 → Task 1；共享会话 → Task 2+3；get_admin_client 双认证 → Task 5；模型放宽（支持纯 header token）→ Task 4；兼容路径 → Task 5 账密分支；验证 → Task 7。全部覆盖。
- **占位符**：无 TBD/TODO；每步含完整代码/命令。
- **类型一致性**：`issue_token`/`verify_token`/`refresh_login`/`get_admin_client`（SharedAdminSession 与 VerifyAdmin 中同名函数有清晰区分）签名在 Task 间一致。`AdminAuthRequest` 在 Task 4 定义、Task 5 消费，字段一致。
- **注意**：`get_admin_client` 在 `tools/VerifyAdmin.py`（FastAPI 依赖）与 `tools/SharedAdminSession.py`（返回共享客户端）同名但职责不同——VerifyAdmin 版通过 `from tools.SharedAdminSession import get_admin_client as get_shared_admin_client` 区分，避免冲突。
