# Claude Code 激活码切 LOCAL NewAPI 实例

> 记录两个 commit 的改动内容、设计决策、env 配置，以及途中遇到的一个 bug 复盘。
>
> - 功能: `c4f3fc5 功能：claude code 激活码的 token 创建/兑换切到 LOCAL NewAPI 实例`
> - Bug fix: `c8473c4 Bug fix：claude code 切 LOCAL 时 ActivationCodeManager 被误切走`

---

## 1. 背景

部署了一个独立的 LOCAL NewAPI 实例（`http://192.168.28.13:25142/`，含独立 PG `@192.168.28.2`），专门用于 **claude code 套餐**。其它套餐（default / vip / svip 等）继续走默认 NewAPI，不受影响。

驱动因素：claude code 套餐是新增的、与默认 NewAPI 隔离的模型白名单+分组，希望 token 数据物理隔离、便于独立运维/计费/审计。

---

## 2. 架构：资源分布

| 资源 | 存哪 | 走的 DB | 走的 NewAPI |
|---|---|---|---|
| `activation_codes` 表 | server A oneapi | `DB_HOST`（默认） | — |
| `tokens`（claude code 创建的） | local oneapi | `DB_HOST_LOCAL` | `NEWAPI_URL_LOCAL` |
| `tokens`（其它套餐创建的） | server A oneapi | `DB_HOST`（默认） | `NEWAPI_URL`（默认） |
| OpenWebUI 登录校验 | openwebui DB | 默认 env | — |

> 关键：用户拿到 claude code 激活码兑换后的 sk-xxx **只能**在 `http://192.168.28.13:25142/` 调，server A 上查不到这条 token（也就 401/404）。这是 by design。

---

## 3. 改动文件清单

| 文件 | 改动类型 | 改动量 |
|---|---|---|
| `tools/DbScript.py` | 改造 | +18 / -10 |
| `services/NewAPIClient.py` | 改造 | +18 / -8 |
| `services/ClaudeCodeActivation.py` | 改造 | +27 / -5 |

---

## 4. 改动细节

### 4.1 `tools/DbScript.py`

`DatabaseManager.__init__` 接受显式 `db_host / db_port / db_user / db_password` 四个 override 参数，**不**自动读 `DB_*_LOCAL` env。

```python
def __init__(self, env_path=".env", db_name="oneapi",
             db_host=None, db_port=None, db_user=None, db_password=None):
    load_dotenv(env_path)
    self.host = db_host or os.getenv("DB_HOST", "localhost")
    self.port = db_port or os.getenv("DB_PORT", "5432")
    self.user = db_user or os.getenv("DB_USERNAME")
    if db_password is not None:
        self.password = db_password
    else:
        self.password = get_decrypted_password("DB_PASSWORD_ENCRYPTED")
    self.dbname = db_name
    self.conn = None
    self.logger = LoggerManager()
```

`NewApiDatabaseManager.__init__` 透传这四个参数给 super。

### 4.2 `services/NewAPIClient.py`

`__init__` 接受 `base_url` 和 `db` 注入：

```python
def __init__(self, base_url: Optional[str] = None, db: Optional[NewApiDatabaseManager] = None):
    load_dotenv()
    self.base_url = (base_url or os.getenv("NEWAPI_URL")).rstrip("/")
    self.session = requests.Session()
    self.session.headers.update({"Content-Type": "application/json"})
    self.user_id = None
    self.db = db
```

`_get_full_token_key_from_db` 改用 `self.db`（None 时回退到默认 NewApiDatabaseManager，向后兼容）：

```python
db = self.db if self.db is not None else NewApiDatabaseManager()
```

### 4.3 `services/ClaudeCodeActivation.py`

新增工厂函数集中组装 LOCAL 资源：

```python
def _get_local_claude_clients() -> tuple["NewAPIClient", "NewApiDatabaseManager"]:
    local_url = os.getenv("NEWAPI_URL_LOCAL")
    if not local_url:
        raise RuntimeError("未配置 NEWAPI_URL_LOCAL，无法兑换 claude code 激活码")
    local_url = local_url.rstrip("/")

    local_db = NewApiDatabaseManager(
        db_host=os.getenv("DB_HOST_LOCAL"),  # 用户在 .env 加 DB_HOST_LOCAL=192.168.28.2
    )
    if local_db.host == "localhost":
        logger.warning(
            "[claude_code] DB_HOST_LOCAL 未配置, LOCAL DB 回退到 localhost; "
            "请确认 .env 里 DB_HOST_LOCAL 是否设置正确"
        )
    local_client = NewAPIClient(base_url=local_url, db=local_db)
    logger.info(
        f"[claude_code] LOCAL 资源就绪: url={local_url}, "
        f"db_host={local_db.host}, db_name={local_db.dbname}"
    )
    return local_client, local_db
```

`redeem_claude_token_after_validation` 把原来两行：

```python
db = NewApiDatabaseManager()
newapiclient = NewAPIClient()
```

替换成：

```python
newapiclient, db = _get_local_claude_clients()
```

其它流程（OpenWebUI 登录、SELECT/UPDATE tokens、create_token、mark_as_used）保持原样。

---

## 5. 必填 .env

```bash
# claude code 切 LOCAL
NEWAPI_URL_LOCAL=http://192.168.28.13:25142/   # ← 缺这个会直接 RuntimeError
DB_HOST_LOCAL=192.168.28.2                     # ← 缺这个会回退到 localhost 并打 warning
```

**不需要**额外加的（与默认共用）：`DB_PORT_LOCAL` / `DB_USERNAME_LOCAL` / `DB_PASSWORD_ENCRYPTED_LOCAL`。本项目 LOCAL 与默认 NewAPI 共用账号密码。

---

## 6. 关键设计点

1. **`DatabaseManager` 不自动读 `DB_*_LOCAL` env**：避免全局副作用污染同进程内其它 `NewApiDatabaseManager()` 调用（例如 `ActivationCodeManager`）。
2. **只有工厂显式传 `db_host`**：调用方明确表达"我要 LOCAL"的意图，env 读取与实际行为解耦。
3. **`client.db` 与工厂 `db` 共享同一个连接**：这样 `create_token` 内部 `_get_full_token_key_from_db` 也会走 LOCAL DB，能拿到新建 token 的完整 sk-xxx（不会拿到 `"***"`）。
4. **OpenWebUI 登录保持不动**：与 NewAPI 是两套系统，claude code 用户体系是 OpenWebUI 那一套。

---

## 7. 端到端验证步骤

1. **生成一个 claude code 激活码**（管理员接口）：
   ```bash
   curl -X POST http://localhost:25141/api/admin/generate-activation-codes \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"xxx","tasks":[["claude code",0,1,1.0]]}'
   ```
   期望：`status=true`, `total_generated=1`, `total_saved=1`, 无 `errors[]`。记下 `codes[0].code`。

2. **拿已注册用户的邮箱+密码，兑换**：
   ```bash
   curl -X POST http://localhost:25141/api/random-activation-code \
     -H "Content-Type: application/json" \
     -d "{\"code\":\"上一步的code\",\"username\":\"x\",\"email\":\"test@x.com\",\"password\":\"xxx\"}"
   ```
   期望：`status=true`，`plan_info.token_key` 是完整 sk-xxx（不是 `***`）。

3. **看 logs**：`logs/claude_code_activation.log` 应出现：
   ```
   [claude_code] LOCAL 资源就绪: url=http://192.168.28.13:25142, db_host=192.168.28.2, db_name=oneapi
   [claude_code] 已新建 Claude Code token: name=Claude Code - test@x.com, quota=...
   ```
   第二次兑换同一 email 应出现 `已累加额度到现有 token: ...` 而不是再建一条。

4. **LOCAL PG（192.168.28.2）查**：
   ```sql
   SELECT id, name, remain_quota, expired_time, model_limits, "group"
     FROM tokens WHERE name = 'Claude Code - <email>';
   ```
   首次兑换：1 行；再次兑换：仍是 1 行，`remain_quota` 累加。

5. **默认 DB（server A）查**：
   ```sql
   SELECT code_id, used_at, used_by FROM activation_codes WHERE code_id = '<code_id>';
   ```
   期望 `used_at` 已被标记。

---

## 8. 故障复盘（Bug fix `c8473c4`）

### 8.1 症状

兑换 claude code 激活码时：

```
ERROR - [find_by_code_id] SQL 执行失败: relation "activation_codes" does not exist
ERROR - [random_code] DB 查询失败（不是激活码不存在）: SQL 执行失败: ...
WARNING - 激活码验证失败: 系统异常：DB 查询失败 ...
```

返回给用户的是 `"激活码不存在或已失效"` 的包装，但实际是 SQL 异常，不是激活码真的不存在。

### 8.2 根因

第一版 (`c4f3fc5`) 把"读 `DB_*_LOCAL` env"的逻辑 bake 进了 `DatabaseManager.__init__`：

```python
# 错误示范（c4f3fc5 初版）
self.host = db_host or os.getenv("DB_HOST_LOCAL") or os.getenv("DB_HOST", "localhost")
```

这样**所有** `NewApiDatabaseManager()` 调用（包括 `ActivationCodeManager.__init__` 里的那个）都会先看 `DB_HOST_LOCAL`，命中就切到 LOCAL。

`ActivationCodeManager` 里的 `find_by_code_id` 跑 `SELECT ... FROM activation_codes ...`，但 `activation_codes` 表只在 lobeai 默认 DB 里 —— LOCAL DB 里没这张表，于是 `relation "activation_codes" does not exist`。

### 8.3 修复

把 `DB_*_LOCAL` 的自动读取从 `DatabaseManager.__init__` 里去掉，让调用方显式传 `db_host`：

```python
# 修复后
self.host = db_host or os.getenv("DB_HOST", "localhost")
```

工厂改为：

```python
local_db = NewApiDatabaseManager(
    db_host=os.getenv("DB_HOST_LOCAL"),  # 显式表达意图
)
```

再加一个 host 回退到 `localhost` 的 warning 日志，方便排查"配了 URL 忘了配 host"的情况。

### 8.4 教训

| 编号 | 教训 |
|---|---|
| 1 | **env-based override 是全局副作用**，会让同进程内所有同类型对象都被影响。Python 习惯是"调用方显式传"而不是"实例自动读 env"。 |
| 2 | 任何"实例初始化时读 env"的设计都要追问一句：**同进程内还有谁会实例化同类对象？** 如果答案是"很多人"（这里 `NewApiDatabaseManager` 有 5+ 个调用点），那 env 读取要慎之又慎。 |
| 3 | bug 的"双撒谎"特征（`save_codes` 说成功 + `execute_command` 说成功 + DB 里没行）非常误导定位。后续类似的 silent failure 应该尽早把 `rowcount` 打日志，区分"没报错"和"没影响行"。 |

---

## 9. 附录：相关文件

- `services/ClaudeCodeActivation.py` — 工厂 + 兑换流程
- `services/RandomActivationCode.py` — 统一入口，按 `plan_level` 路由
- `services/GenerateActivationCodes.py` — 激活码生成（含 RMB→quota 转换）
- `tools/ActivationCodeManager.py` — 激活码的签发/验签/存管
- `tools/DbScript.py` — `DatabaseManager` / `NewApiDatabaseManager`
- `tools/GetNewestRate.py` — USD/CNY 汇率（用于 RMB→quota 转换）
- `data/claude.json` — claude code 套餐的模型白名单
