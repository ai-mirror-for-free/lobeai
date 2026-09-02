"""
激活码兑换服务 —— 仅支持 Claude Code

- plan_level == "claude code" → 调用 ClaudeCodeActivation 的 token 流程
  （创建/累加名为 "Claude Code - {email}" 的 token，三模型白名单，永不过期）
- 其他 plan_level（如历史 default/vip/svip）→ 明确拒绝，且不在 mark_as_used 中消耗

成功才标记激活码为已使用；任一步骤失败激活码保持未用状态。
"""
from tools.LoggerManager import LoggerManager
from tools.ActivationCodeManager import ActivationCodeManager

logger = LoggerManager(log_file="activation_code.log")


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
    2. 仅允许 plan_level == "claude code"，其他类型直接拒绝
    3. Claude Code 路径成功后标记激活码为已使用
    4. 邀请返利：若 email 有 invite_bindings，则给 inviter 加 10% 无封顶

    Args:
        code: 激活码
        username: 用户名（Claude Code 流程忽略）
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

    # 2) 仅允许 Claude Code，其他 plan_level 显式拒绝（不消耗激活码）
    if plan_level != CLAUDE_PLAN_LEVEL:
        logger.warning(
            f"激活码 plan_level={plan_level} 已下线，拒绝兑换 code_id={code_id}, email={email}"
        )
        return {
            "status": False,
            "message": "该激活码对应的套餐已下线，请联系客服更换 Claude Code 激活码",
        }

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

    if not routed.get("status"):
        # 子流程失败 → 激活码保持未用状态
        return routed

    # 3) 仅在子流程全部成功后，才标记激活码为已使用
    manager.mark_as_used(code_id, used_by=email)

    # 3.5) 邀请返利：a 邀 b，b 每次充值 a 得 10% 无封顶（激活码面额口径）
    # 必须在 mark_as_used 之后触发，且失败不影响主流程返回
    try:
        from services.InviteService import (
            get_binding_for_invitee,
            calculate_reward,
            record_reward,
            reward_inviter_via_server_b,
        )
        binding = get_binding_for_invitee(email)
        if binding:
            recharge_quota = int(quota or 0)
            recharge_rmb, reward_rmb, reward_quota = calculate_reward(recharge_quota)
            if reward_quota > 0 and reward_rmb > 0:
                inviter_email = binding.get("inviter_email")
                binding_id = binding.get("id")
                logger.info(f"[invite] 触发返利 invitee={email} inviter={inviter_email} recharge={recharge_rmb} reward={reward_rmb} quota={reward_quota} code={code_id}")
                ok, is_new = record_reward(
                    binding_id=binding_id,
                    invitee_email=email,
                    inviter_email=inviter_email,
                    activation_code_id=code_id,
                    recharge_quota=recharge_quota,
                    recharge_rmb=recharge_rmb,
                    reward_quota=reward_quota,
                    reward_rmb=reward_rmb,
                )
                if not ok:
                    logger.warning(f"[invite] 奖励记录写入失败 invitee={email} code={code_id}")
                elif not is_new:
                    logger.info(f"[invite] 重复兑换已奖励过 invitee={email} code={code_id} 跳过返利")
                else:
                    ok2, msg = reward_inviter_via_server_b(inviter_email, reward_quota, email, code_id)
                    if ok2:
                        logger.info(f"[invite] 返利成功 invitee={email} inviter={inviter_email} +{reward_quota} ({reward_rmb}元) code={code_id}")
                    else:
                        logger.warning(f"[invite] 返利失败 invitee={email} inviter={inviter_email} code={code_id}: {msg}")
            else:
                logger.info(f"[invite] 无需返利 invitee={email} recharge_quota={quota}")
        else:
            logger.info(f"[invite] 无邀请绑定 invitee={email} 跳过返利")
    except Exception as e:
        logger.error(f"[invite] 返利异常 invitee={email} code={code_id}: {e}")

    # 4) 组装响应（透传子流程字段）
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
