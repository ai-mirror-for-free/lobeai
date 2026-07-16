"""
批量生成激活码服务

tasks 元素格式（统一 4 元素）:
  套餐码: [plan_level, days, count, 0]              days ∈ [1, 30, 90]，price 默认 0
  claude:  ["claude code", 0, count, price]         price > 0 (人民币，按实时汇率换成 quota)

claude code 的 price 是人民币，生成时通过汇率转换为 quota 单位
（与 services/BatchCreateTokens.py 同公式: int(price / rate * 500000)），
转换结果作为 activation_code payload 的 quota 字段。
"""
import json
import os
from tools.LoggerManager import LoggerManager
from tools.GetNewestRate import get_usd_cny_rate
from tools.ActivationCodeManager import (
    generate_activation_code,
    ActivationCodeManager,
)

logger = LoggerManager(log_file="activation_code.log")

# claude_code 套餐的 plan_level（与 data/claude.json key 共用）
CLAUDE_PLAN_LEVEL = "claude code"
# 套餐码允许的天数
ALLOWED_DAYS = [1, 30, 90]


def _rmb_to_quota(price_rmb: float) -> int:
    """
    人民币 → quota 额度单位
    与 services/BatchCreateTokens.batch_create_tokens 公式保持一致:
        remain_quota = int(price / rate * 500000)
    """
    rate, local = get_usd_cny_rate()
    if not local:
        logger.warning("[claude_code] 汇率获取失败，使用缓存/默认汇率")
    return int(price_rmb / rate * 500000)


def get_valid_plans():
    """
    激活码的有效 plan_level 列表：
    - pricing_plan.json 中除 free 外的 key
    - 加上 "claude code" (claude_code 激活码专用)

    返回值示例: ["default", "vip", "svip", "claude code"]
    """
    valid = {CLAUDE_PLAN_LEVEL}
    pricing_file = "data/pricing_plan.json"
    try:
        with open(pricing_file, 'r') as f:
            data = json.load(f)
            for p in data.keys():
                if p != "free":
                    valid.add(p)
    except Exception as e:
        logger.error(f"加载 pricing_plan.json 失败: {e}")
        for fallback in ("default", "vip", "svip"):
            valid.add(fallback)
    return list(valid)


def _normalize_task(task: list) -> dict | None:
    """
    解析单个任务元素，返回统一的 dict；非法格式返回 None。

    支持两种任务格式：
      套餐码: [plan_level, days, count]          (legacy 3 元，向后兼容)
      套餐码: [plan_level, days, count, 0]        (显式 price=0)
      claude:  [plan_level, 0, count, price]      (claude code，days 必为 0，price>0)

    返回: {"plan_level", "days", "count", "price_rmb", "task_type"}
          task_type ∈ {"plan", "claude"}
          price_rmb: 输入的人民币价格（套餐码为 0）
    """
    if not isinstance(task, list) or len(task) < 3:
        return None
    plan_level = task[0]
    days = task[1]
    count = task[2]
    price = task[3] if len(task) >= 4 and task[3] is not None else 0

    if not isinstance(plan_level, str):
        return None
    if not isinstance(days, int) or isinstance(days, bool):
        return None
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        return None
    # price 允许 int / float，但禁止 bool；套餐码允许为 0；claude 码要求 > 0
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return None
    price = float(price)
    if price < 0:
        return None

    if price > 0:
        if days != 0:
            return None
        return {
            "plan_level": plan_level,
            "days": 0,
            "count": count,
            "price_rmb": price,
            "task_type": "claude",
        }

    return {
        "plan_level": plan_level,
        "days": days,
        "count": count,
        "price_rmb": 0.0,
        "task_type": "plan",
    }


def batch_generate_activation_codes(
    tasks: list[list]
) -> dict:
    """
    批量生成激活码并存储到数据库

    Args:
        tasks: 每个元素支持
          - [plan_level, days, count]              (套餐码，price 默认 0)
          - [plan_level, days, count, 0]           (套餐码显式 price=0)
          - [plan_level, 0, count, price]          (claude code, price 人民币)

    Returns:
        生成结果摘要（含 details[].price 人民币、details[].quota 实际额度单位、
        codes[].quota 实际额度单位）
    """
    manager = ActivationCodeManager()
    valid_plans = get_valid_plans()

    total_generated = 0
    total_saved = 0
    results = []
    errors = []
    codes_list = []  # 收集所有生成的明文激活码

    for task in tasks:
        normalized = _normalize_task(task)
        if normalized is None:
            msg = f"无效任务格式: {task}"
            logger.error(msg)
            errors.append(msg)
            continue

        plan_level = normalized["plan_level"]
        days = normalized["days"]
        count = normalized["count"]
        price_rmb = normalized["price_rmb"]
        task_type = normalized["task_type"]

        # 校验 plan_level
        if plan_level not in valid_plans:
            msg = f"无效的套餐级别: {plan_level}，有效值为: {valid_plans}"
            logger.error(msg)
            errors.append(msg)
            continue

        # 套餐码额外校验 days
        if task_type == "plan" and days not in ALLOWED_DAYS:
            msg = f"无效的天数: {days}，有效值为: {ALLOWED_DAYS}"
            logger.error(msg)
            errors.append(msg)
            continue

        # claude code 额外校验 price > 0
        if task_type == "claude" and price_rmb <= 0:
            msg = f"claude code 任务的 price 必须 > 0, 收到: {price_rmb}"
            logger.error(msg)
            errors.append(msg)
            continue

        # ── 计算 quota (claude code 需 RMB→quota 转换) ──
        if task_type == "claude":
            quota = _rmb_to_quota(price_rmb)
            logger.info(
                f"claude code 价格转换: price={price_rmb} 元 → quota={quota}"
            )
        else:
            quota = 0  # 套餐码不在激活码里存 quota，额度由 buy_package 按 days×plan_price 现场算

        codes_to_save = []
        for _ in range(count):
            code = generate_activation_code(plan_level, days, quota)

            # 从 code 中解析出 code_id（用于存储）
            from tools.ActivationCodeManager import parse_activation_code
            parsed = parse_activation_code(code)

            codes_to_save.append({
                "code": code,
                "plan_level": plan_level,
                "days": days,
                "quota": quota,
                "code_id": parsed["code_id"],
            })
            total_generated += 1

            # 收集明文激活码用于返回
            codes_list.append({
                "code": code,
                "plan_level": plan_level,
                "days": days,
                "quota": quota,
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

        result_item = {
            "plan_level": plan_level,
            "days": days,
            "task_type": task_type,
            "generated": count,
        }
        if task_type == "claude":
            result_item["price_rmb"] = round(price_rmb, 2)
            result_item["quota"] = quota
            logger.info(
                f"生成 {count} 个 claude code 激活码: "
                f"{plan_level} + price={price_rmb}元 (quota={quota})"
            )
        else:
            logger.info(f"生成 {count} 个套餐激活码: {plan_level} + {days}天")

        results.append(result_item)

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
