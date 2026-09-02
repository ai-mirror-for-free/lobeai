"""
update-user-quota 主数据聚合口（给别的项目用，只读）

数据来源（claude code 统一走 server_b，tokens 表同一账单）：
- 剩余余额：直连 server_b /billing/balance?email= → remain_quota → 人民币
- 累计充值：同一接口的 total_quota（remain+used，token 全部入账额度）→ 人民币。
  与 balance 同源同表，历史/手工/其它途径的额度充值也能体现，
  避免 activation_codes 覆盖不全导致的「充值明显少于已用」。
换算公式：RMB = quota × usd_cny_rate / 500000（与 claude_agent / 兑换链路一致）。

返回按套餐类型打包成 plans 列表，方便未来新增套餐（append 一项即可）：
  {
    "email": "...",
    "currency": "CNY",
    "plans": [
      { "type": "claude code", "balance": 12.34, "total_recharged": 50.0,
        "unlimited": false, "has_key": true }
    ]
  }

只读，不写 users_center（原 days_left / quota_left 写入已废弃）。
"""
from tools.LoggerManager import LoggerManager
from tools.GetNewestRate import get_usd_cny_rate

logger = LoggerManager()

# NewAPI 额度换算单位：500000 quota = 1 USD
QUOTA_TO_USD = 500000

# 当前支持的套餐类型（未来扩展时在此追加构建函数即可）
CLAUDE_CODE = "claude code"


def _server_b_balance(email: str) -> dict:
    """直连 server_b /billing/balance，拿 Claude Code token 的剩余额度

    Returns:
        dict（可能含 remain_quota / unlimited / has_key）；调用失败返回 {}
    """
    import requests
    from services.ClaudeCodeActivation import _server_b_url, _cf_access_headers

    try:
        url = _server_b_url() + "/billing/balance"
        resp = requests.get(
            url, params={"email": email}, timeout=10,
            headers=_cf_access_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"[update-user-quota] server_b /billing/balance 失败: {e}, email={email}")
        return {}


def _quota_to_rmb(quota, rate: float | None = None) -> float:
    """NewAPI 额度 → 人民币（rate 可外部传入，保证单次请求内汇率口径一致）"""
    if not quota:
        return 0.0
    try:
        if rate is None:
            rate, _ = get_usd_cny_rate()
        return round(float(quota) / QUOTA_TO_USD * rate, 2)
    except Exception as e:
        logger.error(f"[update-user-quota] 汇率换算失败: {e}, quota={quota}")
        return 0.0


def _build_plan(plan_type: str, email: str) -> dict:
    """按套餐类型构建一条额度记录

    当前仅 claude code；未来新增套餐时在此扩展对应数据来源。
    """
    if plan_type == CLAUDE_CODE:
        b = _server_b_balance(email)
        remain = b.get("remain_quota")
        unlimited = bool(b.get("unlimited"))
        has_key = bool(b.get("has_key"))
        total_quota = b.get("total_quota")

        # 剩余余额：unlimited 或拿不到 remain 时余额按 0，由 unlimited 标志区分
        balance = 0.0
        if not unlimited and remain is not None:
            balance = _quota_to_rmb(remain)

        # 累计充值 = token 全部入账额度（remain+used，与 balance 同源同表）。
        # 历史/手工/其它途径的额度充值也计入，避免 activation_codes 覆盖不全
        total_recharged = 0.0
        if not unlimited and total_quota is not None:
            total_recharged = _quota_to_rmb(total_quota)

        balance_warning = b.get("balance_warning") or {"enabled": False, "message": None}
        return {
            "type": CLAUDE_CODE,
            "balance": balance,
            "total_recharged": total_recharged,
            "unlimited": unlimited,
            "has_key": has_key,
            "balance_warning": balance_warning,
        }

    logger.error(f"[update-user-quota] 未知套餐类型: {plan_type}, email={email}")
    return {
        "type": plan_type,
        "balance": 0.0,
        "total_recharged": 0.0,
        "unlimited": False,
        "has_key": False,
        "balance_warning": {"enabled": False, "message": None},
    }


def get_user_info(username, email):
    """
    查询用户额度（人民币，只读），按套餐类型打包为 plans 列表
    """
    plans = [_build_plan(CLAUDE_CODE, email)]

    result = {
        "email": email,
        "currency": "CNY",
        "plans": plans,
    }
    logger.info(f"[update-user-quota] result email={email} → {result}")
    return result
