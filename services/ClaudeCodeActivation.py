"""
claude_code 激活码兑换核心模块（2026-07-23/24 委派给 server_b）

本模块对外暴露两个函数（保持原有签名 + 返回结构不变）：
- redeem_claude_activation_code(code, email, password) —— 独立完整入口（自己验证激活码）
- redeem_claude_token_after_validation(code_id, code, email, password, quota)
  —— 仅执行「调 server_b → 拿到 token 字段」，调用方负责 random_code 验证
  用于在 RandomActivationCode 的统一入口里按 plan_level 路由时复用。

2026-07-24 修订：lobeai → server_b 透传的是 NewAPI 管理员账号（不是用户密码）。
B 侧 NewAPI 创建 token 必须用管理员账号（NewAPI 设计上不允许用户自建 token；
B 侧 users 表里至始至终只有管理员自己一个用户；所有 Claude Code key 都是
管理员创建并归属到管理员账号下）。lobeai 从 .env 的 NEWAPI_USER +
Fernet 解密 NEWAPI_PASSWORD_ENCRYPTED 得到管理员明文。
- email 字段只用于给 token 命名（"Claude Code - <email>"）
- 用户真实性由 lobeai 端的 ActivationCodeManager.random_code + 激活码签名保证

注意: 本模块流程与 RandomActivationCode.random_activation_code 中的套餐码分支互斥，
      但复用同一个 ActivationCodeManager.mark_as_used（外层 RandomActivationCode 行 154
      会在子流程返回 status:true 之后调用；本模块不再内嵌 mark_as_used）。
"""
import json
import os

import requests

from tools.LoggerManager import LoggerManager
from tools.password_encryption import get_decrypted_password

logger = LoggerManager(log_file="claude_code_activation.log")

# 与 data/claude.json / 新激活码 payload 共用的常量
CLAUDE_PLAN_LEVEL = "claude code"     # 激活码 plan_level + NewAPI token group
NAME_PREFIX = "Claude Code - "        # NewAPI token name 前缀

# admin 凭据 env 名（2026-07-24 改用 ADMIN_USERNAME/ADMIN_PASSWORD_ENCRYPTED，
# 与 tools.VerifyAdmin.get_admin_client 一致；ENCRYPTION_KEY 通过 SSH 注入进程 env）
_ADMIN_USER_ENV = "ADMIN_USERNAME"
_ADMIN_PASSWORD_ENCRYPTED_ENV = "ADMIN_PASSWORD_ENCRYPTED"


def _server_b_url() -> str:
    """从 .env 读 SERVER_B_URL；缺则抛 RuntimeError（fail-fast，避免静默）"""
    url = (os.getenv("SERVER_B_URL") or "").rstrip("/")
    if not url:
        raise RuntimeError(
            "未配置 SERVER_B_URL，lobeai 无法委派 Claude Code 兑换给 server_b；"
            "请在 .env 加 SERVER_B_URL=https://mirror.chat-keeper.com"
        )
    return url


def _load_claude_models() -> list[str]:
    """从 data/claude.json 加载 claude 套餐的模型列表（透传给 server_b）"""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "claude.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["claude"]


def _resolve_admin_credentials() -> tuple[str, str]:
    """从 .env 解析 NewAPI 管理员账号明文

    Returns:
        (admin_user, admin_password_plain)
    Raises:
        RuntimeError 缺凭据时抛
    """
    admin_user = os.getenv(_ADMIN_USER_ENV)
    admin_password = None
    try:
        admin_password = get_decrypted_password(_ADMIN_PASSWORD_ENCRYPTED_ENV)
    except Exception as e:
        raise RuntimeError(
            f"无法解密 {_ADMIN_PASSWORD_ENCRYPTED_ENV}，请检查 .env 与 "
            f"ENCRYPTION_KEY 是否一致: {e}"
        )
    if not admin_user or not admin_password:
        raise RuntimeError(
            f"lobeai 管理员凭据不完整：{_ADMIN_USER_ENV} 或 "
            f"{_ADMIN_PASSWORD_ENCRYPTED_ENV} 未设置"
        )
    return admin_user, admin_password


def _call_server_b_redeem(
    code_id: str,
    email: str,
    quota: int,
    model_limits: str,
) -> dict:
    """HTTP POST server_b /activation/redeem；超时 / 协议失败 → {status: false, ...}

    透传给 server_b 的是 lobeai 持有的 NewAPI 管理员账号（不是用户密码）；
    server_b 用它登录 B 侧 NewAPI 创建/累加属于该 email 的 token。

    Returns:
        业务成功 → {status: True, token_key, name, group, model_limits,
                   expired_time, quota_added, quota_total, activation_code_id}
        业务失败 → {status: False, message: "..."}
    """
    admin_user, admin_password = _resolve_admin_credentials()

    url = _server_b_url() + "/activation/redeem"
    payload = {
        "activation_code_id": code_id,
        "email": email,
        "admin_user": admin_user,
        "admin_password": admin_password,
        "quota": int(quota),
        "model_limits": model_limits,
        "name_prefix": NAME_PREFIX,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
    except requests.exceptions.Timeout:
        logger.error(f"[claude_code] server_b 超时: email={email}")
        return {"status": False, "message": "B 侧兑换超时，请稍后重试"}
    except requests.exceptions.RequestException as e:
        logger.error(f"[claude_code] server_b 不可达: {e}, email={email}")
        return {"status": False, "message": f"B 侧服务不可达: {e}"}

    try:
        data = resp.json()
    except Exception as e:
        logger.error(
            f"[claude_code] server_b 返回非 JSON: status={resp.status_code}, "
            f"err={e}, email={email}"
        )
        return {"status": False, "message": "B 侧返回格式异常"}

    if resp.status_code >= 400:
        msg = (
            data.get("message")
            or data.get("error")
            or data.get("detail")
            or f"HTTP {resp.status_code}"
        )
        logger.error(
            f"[claude_code] server_b HTTP {resp.status_code}: {msg}, email={email}"
        )
        return {"status": False, "message": f"B 侧兑换失败: {msg}"}

    if not isinstance(data, dict) or "status" not in data:
        logger.error(
            f"[claude_code] server_b 响应缺 status 字段: {data}, email={email}"
        )
        return {"status": False, "message": "B 侧响应格式异常"}

    return data


def redeem_claude_token_after_validation(
    code_id: str,
    code: str,
    email: str,
    password: str,
    quota: int,
) -> dict:
    """在激活码 random_code 验证通过且 quota>0 后，委派 server_b 完成 token 操作。

    Args:
        code_id: 已验证的激活码 code_id
        code:    原始激活码（仅做日志/调试用）
        email:   用户邮箱（仅用于命名 token）
        password:用户密码（Claude 分支不使用，保留仅为了兼容 RandomActivationCode 签名）
        quota:   额度（int）

    Returns:
        {"status": True, "token_key": "...", "quota_added": ..., ...} 成功
        {"status": False, "message": "..."} 失败（此时不调用 mark_as_used，激活码仍可用）

    注意：成功后激活码的 mark_as_used 由外层 RandomActivationCode.random_activation_code
          行 154 统一执行；本函数不再内嵌 mark_as_used，避免重复。
    """
    if not code_id or not email or not quota or quota <= 0:
        logger.error(
            f"[claude_code] 参数非法: code_id={code_id}, email={email}, quota={quota}"
        )
        return {"status": False, "message": "兑换参数非法"}

    model_list = _load_claude_models()
    model_limits_str = ",".join(model_list)

    logger.info(
        f"[claude_code] 委派 server_b: code_id={code_id}, email={email}, quota={quota}"
    )
    result = _call_server_b_redeem(
        code_id=code_id,
        email=email,
        quota=int(quota),
        model_limits=model_limits_str,
    )

    if result.get("status"):
        logger.info(
            f"[claude_code] 用户充值成功: email={email}, "
            f"quota_added={result.get('quota_added')}, "
            f"quota_total={result.get('quota_total')}"
        )
    else:
        logger.warning(
            f"[claude_code] 兑换失败: email={email}, message={result.get('message')}"
        )

    return result


def redeem_claude_activation_code(code: str, email: str, password: str) -> dict:
    """兑换 claude_code 激活码（独立完整入口）

    流程:
    1. random_code 验证激活码（含签名、DB 匹配、未使用校验）
    2. 校验 plan_level == CLAUDE_PLAN_LEVEL、quota > 0
    3. 调用 redeem_claude_token_after_validation 执行 token 操作（委派 server_b）
    """
    from tools.ActivationCodeManager import ActivationCodeManager

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

    # 4) token 操作（成功后才 mark_as_used；mark_as_used 由 RandomActivationCode 外层调）
    return redeem_claude_token_after_validation(
        code_id=code_id,
        code=code,
        email=email,
        password=password,
        quota=quota,
    )