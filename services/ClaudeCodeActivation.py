"""
claude_code 激活码兑换核心模块

本模块对外暴露两个函数：
- redeem_claude_activation_code(code, email, password) —— 独立完整入口（自己验证激活码）
- redeem_claude_token_after_validation(code_id, code, email, password, quota)
  —— 仅执行「登录 + token 创建/累加 + 标记已使用」，调用方负责 random_code 验证
    用于在 RandomActivationCode 的统一入口里按 plan_level 路由时复用。

注意: 本模块流程与 RandomActivationCode.random_activation_code 中的套餐码分支互斥，
      但复用同一个 ActivationCodeManager.mark_as_used。
"""
import json
import os

from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager
from tools.ActivationCodeManager import ActivationCodeManager
from services.NewAPIClient import NewAPIClient, TokenConfig
from services.OpenWebuiAuth import get_jwt_token

logger = LoggerManager(log_file="claude_code_activation.log")

# 与 data/claude.json / 新激活码 payload 共用的常量
CLAUDE_PLAN_LEVEL = "claude code"     # 激活码 plan_level + NewAPI token group
NAME_PREFIX = "Claude Code - "        # NewAPI token name 前缀


def _get_local_claude_clients() -> tuple["NewAPIClient", "NewApiDatabaseManager"]:
    """
    组装 claude code 专用的 NewAPIClient + NewApiDatabaseManager（指向 LOCAL 实例）

    通过显式 db_host=os.getenv("DB_HOST_LOCAL") 让 NewApiDatabaseManager 连 LOCAL 的 PG。
    注意: DB_*_LOCAL env 不会被 DatabaseManager 自动读取, 必须由调用方显式传入
    (否则同进程内所有 NewApiDatabaseManager() 都会被切走, 污染 ActivationCodeManager)。
    user/password/port 走默认 env (本项目 LOCAL 与默认 NewAPI 共用账号密码)。

    client.db 与 db 共享同一个 LOCAL 连接, 这样 create_token 内部
    _get_full_token_key_from_db 也会自动走 LOCAL DB, 拿到完整 sk-xxx (不会拿成 "***")。
    """
    local_url = os.getenv("NEWAPI_URL_LOCAL")
    if not local_url:
        raise RuntimeError("未配置 NEWAPI_URL_LOCAL，无法兑换 claude code 激活码")
    local_url = local_url.rstrip("/")

    local_db = NewApiDatabaseManager(
        db_host=os.getenv("DB_HOST_LOCAL"),  # 用户在 .env 加 DB_HOST_LOCAL=192.168.28.2
    )
    if local_db.host == "localhost":
        # 显式提醒: 配了 NEWAPI_URL_LOCAL 但忘了配 DB_HOST_LOCAL
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


def _load_claude_models() -> list[str]:
    """从 data/claude.json 加载 claude 套餐的模型列表"""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "claude.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["claude"]


def redeem_claude_token_after_validation(
    code_id: str,
    code: str,
    email: str,
    password: str,
    quota: int,
) -> dict:
    """
    在激活码 random_code 验证通过且 quota>0 后，执行 token 流程 + 标记已使用。

    流程:
    1. OpenWebUI 登录校验
    2. 查 tokens WHERE name="Claude Code - {email}" AND deleted_at IS NULL
       - 存在 → UPDATE remain_quota += quota（继承 key）
       - 不存在 → create_token（永不过期、三模型白名单、group="claude code"）
    3. 标记激活码已使用

    Args:
        code_id: 已验证的激活码 code_id（用于 mark_as_used）
        code: 原始激活码（仅做日志/调试用）
        email: 用户邮箱（同时用于 token name 唯一标识）
        password: 用户密码（用于 OpenWebUI 登录校验）
        quota: 从激活码解析出的实际额度单位
                （生成时已由 GenerateActivationCodes._rmb_to_quota 把 RMB 换算过来，
                 与 BatchCreateTokens 公式一致: int(price / rate * 500000)）

    Returns:
        {"status": True, "token_key": "...", "quota_added": ..., ...} 成功
        {"status": False, "message": "..."} 失败（此时不调用 mark_as_used，激活码仍可用）
    """
    model_list = _load_claude_models()
    model_limits_str = ",".join(model_list)
    name = f"{NAME_PREFIX}{email}"

    # ── 1) OpenWebUI 登录校验 ──
    try:
        get_jwt_token(email, password)
    except Exception as e:
        logger.error(f"[claude_code] 用户登录失败: {e}, email={email}")
        return {"status": False, "message": f"用户登录失败: {e}"}

    # ── 2) token 操作（全部走 LOCAL 实例） ──
    newapiclient, db = _get_local_claude_clients()

    db.connect()
    rows = db.execute_query(
        "SELECT id, key, remain_quota FROM tokens "
        "WHERE name = %s AND deleted_at IS NULL",
        (name,),
    )
    db.disconnect()

    newapiclient.login()
    try:
        if rows:
            # 2a) 继承 key：累加 remain_quota
            token_id, token_key, existing_remain = rows[0]
            new_remain_quota = int(existing_remain or 0) + quota
            db.connect()
            db.execute_command(
                "UPDATE tokens SET remain_quota = %s WHERE id = %s",
                (new_remain_quota, token_id),
            )
            db.disconnect()
            logger.info(
                f"[claude_code] 已累加额度到现有 token: id={token_id}, "
                f"existing={existing_remain} + {quota} = {new_remain_quota}, email={email}"
            )
        else:
            # 2b) 新建 token
            trail_token = newapiclient.create_token(
                TokenConfig(
                    name=name,
                    remain_quota=quota,
                    expired_time=-1,                  # 永不过期
                    unlimited_quota=False,
                    model_limits_enabled=True,
                    model_limits=model_limits_str,
                    group=CLAUDE_PLAN_LEVEL,          # "claude code"
                )
            )
            token_key = trail_token.get("key")
            new_remain_quota = quota
            if not token_key or token_key == "***":
                raise RuntimeError(
                    f"无法获取有效的 token key: id={trail_token.get('id')}"
                )
            logger.info(
                f"[claude_code] 已新建 Claude Code token: name={name}, "
                f"quota={quota}, email={email}"
            )
    finally:
        newapiclient.logout()

    # ── 3) 标记激活码已使用（先成功后置；上面失败不会调用这里） ──
    manager = ActivationCodeManager()
    manager.mark_as_used(code_id, used_by=email)
    logger.info(
        f"[claude_code] 用户充值成功: email={email}, "
        f"quota={quota}, total={new_remain_quota}"
    )

    return {
        "status": True,
        "message": "激活成功",
        "token_key": token_key,
        "name": name,
        "group": CLAUDE_PLAN_LEVEL,
        "model_limits": model_limits_str,
        "expired_time": -1,
        "quota_added": quota,
        "quota_total": new_remain_quota,
    }


def redeem_claude_activation_code(code: str, email: str, password: str) -> dict:
    """
    兑换 claude_code 激活码（独立完整入口）

    流程:
    1. random_code 验证激活码（含签名、DB 匹配、未使用校验）
    2. 校验 plan_level == CLAUDE_PLAN_LEVEL、quota > 0
    3. 调用 redeem_claude_token_after_validation 执行 token 操作
    """
    manager = ActivationCodeManager()

    # 1) 验证激活码 (不标记已使用)
    success, message, plan_info = manager.random_code(code, used_by=email)
    if not success:
        logger.warning(f"[claude_code] 激活码验证失败: {message}, email={email}")
        return {"status": False, "message": message}

    plan_level = plan_info["plan_level"]
    code_id = plan_info["code_id"]
    quota = int(plan_info.get("quota", 0) or 0)

    # 2) plan_level 必须为 claude code
    if plan_level != CLAUDE_PLAN_LEVEL:
        logger.error(
            f"[claude_code] 激活码类型错误: plan_level={plan_level}, "
            f"expected={CLAUDE_PLAN_LEVEL}, email={email}"
        )
        return {
            "status": False,
            "message": f"该激活码非 claude code 类型 (plan_level={plan_level})",
        }

    # 3) quota 必须 > 0
    if quota <= 0:
        logger.error(f"[claude_code] 激活码 quota 无效: {quota}, email={email}")
        return {"status": False, "message": "激活码额度无效"}

    # 4) token 操作 + mark_as_used
    return redeem_claude_token_after_validation(
        code_id=code_id,
        code=code,
        email=email,
        password=password,
        quota=quota,
    )
