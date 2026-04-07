"""
批量生成激活码服务
根据 plan_level × days 组合批量生成激活码并存储到数据库

使用方式:
    from services.GenerateActivationCodes import batch_generate_activation_codes
    batch_generate_activation_codes(
        plan_levels=["default", "vip", "svip"],
        days_list=[1, 30, 90],
        counts={"default_1": 10, "default_30": 5, ...}
    )
"""
from tools.LoggerManager import LoggerManager
from tools.ActivationCodeManager import (
    generate_activation_code,
    ActivationCodeManager,
)

logger = LoggerManager(log_file="activation_code.log")


def batch_generate_activation_codes(
    plan_levels: list[str],
    days_list: list[int],
    counts: dict[str, int] = None,
) -> dict:
    """
    批量生成激活码并存储到数据库

    Args:
        plan_levels: 套餐级别列表，如 ["default", "vip", "svip"]
        days_list: 天数列表，如 [1, 30, 90]
        counts: 每个组合的生成数量，key 格式为 "{plan_level}_{days}"，如 "vip_30"
                如果不提供，则每个组合默认生成 10 个

    Returns:
        生成结果摘要
    """
    manager = ActivationCodeManager()

    default_count = 10
    total_generated = 0
    total_saved = 0
    results = []

    for plan_level in plan_levels:
        for days in days_list:
            key = f"{plan_level}_{days}"
            count = (counts or {}).get(key, default_count)

            codes_to_save = []
            for i in range(count):
                code = generate_activation_code(plan_level, days)

                # 从 code 中解析出 code_id（用于存储）
                from tools.ActivationCodeManager import parse_activation_code
                parsed = parse_activation_code(code)

                codes_to_save.append({
                    "code": code,
                    "plan_level": plan_level,
                    "days": days,
                    "code_id": parsed["code_id"],
                })
                total_generated += 1

                # 每100条批量存储
                if len(codes_to_save) >= 100:
                    manager.save_codes(codes_to_save)
                    total_saved += len(codes_to_save)
                    codes_to_save = []

            # 剩余的也存进去
            if codes_to_save:
                manager.save_codes(codes_to_save)
                total_saved += len(codes_to_save)

            results.append({
                "plan_level": plan_level,
                "days": days,
                "generated": count,
            })
            logger.info(f"生成 {count} 个激活码: {plan_level} + {days}天")

    logger.info(f"批量生成完成: 共 {total_generated} 个，存入 DB {total_saved} 个")

    return {
        "status": True,
        "total_generated": total_generated,
        "total_saved": total_saved,
        "details": results,
    }
