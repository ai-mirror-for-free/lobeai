"""
批量生成激活码服务（仅 Claude Code）

tasks 元素格式:
  claude: ["claude code", 0, count, price]   price > 0 (人民币，按实时汇率换成 quota)

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

# claude_code 套餐的固定 plan_level
CLAUDE_PLAN_LEVEL = "claude code"


def _rmb_to_quota(price_rmb: float) -> int:
    """
    人民币 → quota 额度单位
    quota 向上取整 (int(...) + 1)，保证用户实际额度不低于付款价值:
        remain_quota = int(price / rate * 500000) + 1
    """
    rate, local = get_usd_cny_rate()
    if not local:
        logger.warning("[claude_code] 汇率获取失败，使用缓存/默认汇率")
    return int(price_rmb / rate * 500000) + 1


def _normalize_task(task: list) -> dict | None:
    """
    解析单个任务元素，返回统一的 dict；非法格式返回 None。

    仅支持 Claude Code 格式:
      claude: [plan_level, 0, count, price]      (days 必为 0, price>0)

    返回: {"plan_level", "days", "count", "price_rmb", "task_type"}
          task_type 固定为 "claude"
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
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return None
    price = float(price)
    if price <= 0:
        return None
    if plan_level != CLAUDE_PLAN_LEVEL:
        return None
    if days != 0:
        return None

    return {
        "plan_level": plan_level,
        "days": 0,
        "count": count,
        "price_rmb": price,
        "task_type": "claude",
    }


def batch_generate_activation_codes(
    tasks: list[list]
) -> dict:
    """
    批量生成激活码并存储到数据库

    Args:
        tasks: 每个元素仅支持
          - ["claude code", 0, count, price]      (claude code, price 人民币)

    Returns:
        生成结果摘要（含 details[].price 人民币、details[].quota 实际额度单位、
        codes[].quota 实际额度单位）
    """
    manager = ActivationCodeManager()

    total_generated = 0
    total_saved = 0
    results = []
    errors = []
    codes_list = []  # 收集所有生成的明文激活码

    for task in tasks:
        normalized = _normalize_task(task)
        if normalized is None:
            msg = (
                f"无效任务格式: {task}。"
                f"当前仅支持 Claude Code 格式 [\"claude code\", 0, count, price] (price>0)，"
                f"套餐激活码已下线。"
            )
            logger.error(msg)
            errors.append(msg)
            continue

        plan_level = normalized["plan_level"]
        days = normalized["days"]
        count = normalized["count"]
        price_rmb = normalized["price_rmb"]
        task_type = normalized["task_type"]

        # ── 计算 quota (claude code 需 RMB→quota 转换) ──
        quota = _rmb_to_quota(price_rmb)
        logger.info(
            f"claude code 价格转换: price={price_rmb} 元 → quota={quota}"
        )

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
                save_result = manager.save_codes(codes_to_save)
                total_saved += len(save_result.get("success", []))
                if save_result.get("failed"):
                    for f in save_result["failed"]:
                        errors.append(
                            f"INSERT 失败: code_id={f['code_id'][:16]}..., {f['reason']}"
                        )
                codes_to_save = []

        # 剩余的也存进去
        if codes_to_save:
            save_result = manager.save_codes(codes_to_save)
            total_saved += len(save_result.get("success", []))
            if save_result.get("failed"):
                for f in save_result["failed"]:
                    errors.append(
                        f"INSERT 失败: code_id={f['code_id'][:16]}..., {f['reason']}"
                    )

        result_item = {
            "plan_level": plan_level,
            "days": days,
            "task_type": task_type,
            "generated": count,
            "price_rmb": round(price_rmb, 2),
            "quota": quota,
        }
        logger.info(
            f"生成 {count} 个 claude code 激活码: "
            f"{plan_level} + price={price_rmb}元 (quota={quota})"
        )
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
