"""
激活码兑换服务 —— 统一入口，按 plan_level 自动路由

- plan_level == "claude code" → 调用 ClaudeCodeActivation 的 token 流程
  （创建/累加名为 "Claude Code - {email}" 的 token，三模型白名单，永不过期）
- 其他 plan_level → 走原有 buy_package 充值套餐流程

成功才标记激活码为已使用；任一步骤失败激活码保持未用状态。
"""
from tools.LoggerManager import LoggerManager
from tools.ActivationCodeManager import ActivationCodeManager
from func.PricingProcess import fill_pricing_plan

logger = LoggerManager(log_file="activation_code.log")


def _redeem_plan(
    plan_level: str,
    days: int,
    username: str,
    email: str,
    password: str,
) -> dict:
    """
    兑换套餐码（走 buy_package）
    返回: {"status": bool, "message": ...}
    """
    PRICING_PLAN = fill_pricing_plan()

    if plan_level not in PRICING_PLAN:
        logger.error(f"激活码 plan_level 非法: {plan_level}")
        return {"status": False, "message": f"激活码套餐级别错误: {plan_level}"}

    from services.BuyPackageRequest import buy_package
    try:
        result = buy_package(
            username=username,
            email=email,
            password=password,
            plan_level=plan_level,
            days=days,
        )
        if not result.get("status"):
            logger.error(
                f"buy_package 失败: {result.get('message')}, email={email}"
            )
            return {
                "status": False,
                "message": f"充值失败: {result.get('message')}，请联系客服处理",
            }
    except Exception as e:
        logger.error(f"buy_package 异常: {e}, email={email}")
        return {
            "status": False,
            "message": f"充值过程异常: {str(e)}，请联系客服处理",
        }
    return {"status": True}


def _redeem_claude(
    code_id: str,
    code: str,
    email: str,
    password: str,
    quota: int,
) -> dict:
    """
    兑换 claude_code 激活码（走 ClaudeCodeActivation）
    """
    from services.ClaudeCodeActivation import (
        CLAUDE_PLAN_LEVEL,
        redeem_claude_token_after_validation,
    )
    try:
        return redeem_claude_token_after_validation(
            code_id=code_id,
            code=code,
            email=email,
            password=password,
            quota=quota,
        )
    except Exception as e:
        logger.error(f"[claude_code] 兑换异常: {e}, email={email}")
        return {"status": False, "message": f"兑换异常: {e}"}


def random_activation_code(
    code: str,
    username: str,
    email: str,
    password: str,
) -> dict:
    """
    兑换激活码

    流程:
    1. random_code 验证激活码 + 查库确认未使用 (不标记已用)
    2. 根据 plan_level 自动路由:
       - "claude code"  → 创建/累加 NewAPI token "Claude Code - {email}"
       - 其他 plan_level → 调用 buy_package 充值套餐
    3. 路由后的流程成功才标记激活码为已使用

    Args:
        code: 激活码
        username: 用户名（套餐码流程需要，claude code 流程忽略）
        email: 用户邮箱（同时用于 token name 唯一标识）
        password: 用户密码

    Returns:
        兑换结果
    """
    manager = ActivationCodeManager()
    from services.ClaudeCodeActivation import CLAUDE_PLAN_LEVEL

    # 1) 验证激活码（不标记已使用）
    success, message, plan_info = manager.random_code(code, used_by=email)
    if not success:
        logger.warning(f"激活码验证失败: {message}, email={email}")
        return {"status": False, "message": message}

    plan_level = plan_info["plan_level"]
    code_id = plan_info["code_id"]
    days = plan_info.get("days", 0)
    quota = int(plan_info.get("quota", 0) or 0)

    # 2) 按 plan_level 路由
    if plan_level == CLAUDE_PLAN_LEVEL:
        # claude_code 路径
        if quota <= 0:
            logger.error(f"[claude_code] 激活码 quota 无效: {quota}, email={email}")
            return {"status": False, "message": "激活码额度无效"}
        routed = _redeem_claude(
            code_id=code_id,
            code=code,
            email=email,
            password=password,
            quota=quota,
        )
    else:
        # 套餐码路径
        routed = _redeem_plan(
            plan_level=plan_level,
            days=days,
            username=username,
            email=email,
            password=password,
        )

    if not routed.get("status"):
        # 任一子流程失败 → 激活码保持未用状态
        return routed

    # 3) 仅在子流程全部成功后，才标记激活码为已使用
    manager.mark_as_used(code_id, used_by=email)

    # 4) 组装响应
    if plan_level == CLAUDE_PLAN_LEVEL:
        # claude_code 响应（透传子流程字段）
        return {
            "status": True,
            "message": routed.get("message", "激活成功"),
            "plan_info": {
                "plan_level": plan_level,
                "token_key": routed.get("token_key"),
                "name": routed.get("name"),
                "group": routed.get("group"),
                "model_limits": routed.get("model_limits"),
                "expired_time": routed.get("expired_time"),
                "quota_added": routed.get("quota_added"),
                "quota_total": routed.get("quota_total"),
            },
        }

    # 套餐码响应（保持原有结构，向后兼容）
    return {
        "status": True,
        "message": "激活成功",
        "plan_info": {
            "plan_level": plan_level,
            "days": days,
        },
    }
