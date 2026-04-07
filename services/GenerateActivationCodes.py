import json
import os
from tools.LoggerManager import LoggerManager
from tools.ActivationCodeManager import (
    generate_activation_code,
    ActivationCodeManager,
)

logger = LoggerManager(log_file="activation_code.log")


def get_valid_plans():
    """从 pricing_plan.json 获取有效的套餐级别（不包括 free）"""
    pricing_file = "data/pricing_plan.json"
    try:
        with open(pricing_file, 'r') as f:
            data = json.load(f)
            return [p for p in data.keys() if p != "free"]
    except Exception as e:
        logger.error(f"加载 pricing_plan.json 失败: {e}")
        return ["default", "vip", "svip"]  # 备选默认值


def batch_generate_activation_codes(
    tasks: list[list]
) -> dict:
    """
    批量生成激活码并存储到数据库

    Args:
        tasks: 格式为 [[plan_level, days, count], ...]

    Returns:
        生成结果摘要
    """
    manager = ActivationCodeManager()
    valid_plans = get_valid_plans()
    allowed_days = [1, 30, 90]

    total_generated = 0
    total_saved = 0
    results = []
    errors = []
    codes_list = []  # 收集所有生成的明文激活码

    for task in tasks:
        if len(task) < 3:
            msg = f"无效任务格式: {task}"
            logger.error(msg)
            errors.append(msg)
            continue

        plan_level, days, count = task[0], task[1], task[2]

        # 校验 plan_level
        if plan_level not in valid_plans:
            msg = f"无效的套餐级别: {plan_level}，有效值为: {valid_plans}"
            logger.error(msg)
            errors.append(msg)
            continue

        # 校验 days
        if days not in allowed_days:
            msg = f"无效的天数: {days}，有效值为: {allowed_days}"
            logger.error(msg)
            errors.append(msg)
            continue

        codes_to_save = []
        for _ in range(count):
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

            # 收集明文激活码用于返回
            codes_list.append({
                "code": code,
                "plan_level": plan_level,
                "days": days,
            })

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

    response = {
        "status": len(errors) == 0,
        "total_generated": total_generated,
        "total_saved": total_saved,
        "details": results,
        "codes": codes_list,
    }
    if errors:
        response["errors"] = errors

    return response
