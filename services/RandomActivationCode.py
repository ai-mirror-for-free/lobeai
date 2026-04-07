"""
激活码兑换服务
验证激活码 → 调用 buy_package 充值 → 删除激活码
"""
from tools.LoggerManager import LoggerManager
from tools.ActivationCodeManager import ActivationCodeManager
from tools.PricingProcess import fill_pricing_plan

logger = LoggerManager(log_file="activation_code.log")


def random_activation_code(
    code: str,
    username: str,
    email: str,
    password: str,
) -> dict:
    """
    兑换激活码

    流程:
    1. 验证激活码合法性 + 查库确认未使用
    2. 调用 buy_package 完成充值（失败则激活码保持未使用状态）
    3. 充值成功后标记激活码为已使用

    Args:
        code: 激活码
        username: 用户名
        email: 用户邮箱
        password: 用户密码

    Returns:
        兑换结果
    """
    manager = ActivationCodeManager()
    PRICING_PLAN = fill_pricing_plan()

    # 1. 验证激活码（不标记已使用）
    success, message, plan_info = manager.random_code(code, used_by=email)

    if not success:
        logger.warning(f"激活码验证失败: {message}, email={email}")
        return {"status": False, "message": message}

    plan_level = plan_info["plan_level"]
    days = plan_info["days"]
    code_id = plan_info["code_id"]

    # 验证 plan_level 合法性
    if plan_level not in PRICING_PLAN:
        logger.error(f"激活码 plan_level 非法: {plan_level}")
        return {"status": False, "message": f"激活码套餐级别错误: {plan_level}"}

    # 2. 调用 buy_package 充值（先充值，失败则激活码保持未使用）
    try:
        from services.BuyPackageRequest import buy_package
        result = buy_package(
            username=username,
            email=email,
            password=password,
            plan_level=plan_level,
            days=days,
        )
        if not result.get("status"):
            logger.error(f"buy_package 调用失败: {result.get('message')}, email={email}")
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

    # 3. 充值成功后，标记激活码为已使用
    manager.mark_as_used(code_id, used_by=email)
    logger.info(f"用户充值成功: email={email}, plan={plan_level}, days={days}")

    return {
        "status": True,
        "message": "激活成功",
        "plan_info": {
            "plan_level": plan_level,
            "days": days,
        },
    }
