"""
update-user-quota 主数据聚合口（给别的项目用，只读）

数据来源：
- 剩余余额：直连 server_b /billing/balance?email= → remain_quota → 人民币
- 累计充值：lobeai 自己库 activation_codes WHERE used_by=email 的 SUM(quota) → 人民币
换算公式：RMB = quota × usd_cny_rate / 500000（与 claude_agent / 兑换链路一致）

返回全人民币，不再写 users_center（原 days_left / quota_left 写入已废弃）。
"""
from tools.LoggerManager import LoggerManager
from tools.GetNewestRate import get_usd_cny_rate
from tools.DbScript import NewApiDatabaseManager

logger = LoggerManager()

# NewAPI 额度换算单位：500000 quota = 1 USD
QUOTA_TO_USD = 500000


def _server_b_balance(email: str) -> dict:
    """直连 server_b /billing/balance，拿 Claude Code token 的剩余额度

    Returns:
        dict（可能含 remain_quota / unlimited / has_key）；调用失败返回 {}
    """
    import requests
    from services.ClaudeCodeActivation import _server_b_url

    url = _server_b_url() + "/billing/balance"
    try:
        resp = requests.get(url, params={"email": email}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"[update-user-quota] server_b /billing/balance 失败: {e}, email={email}")
        return {}


def _total_recharged_quota(email: str) -> int:
    """累计充值额度：lobeai 自己库 activation_codes 对应用户已兑换 quota 求和"""
    db = NewApiDatabaseManager()
    db.connect()
    try:
        rows = db.execute_query(
            "SELECT COALESCE(SUM(quota), 0) FROM activation_codes WHERE used_by = %s",
            (email,),
        )
        if rows and rows[0] and rows[0][0] is not None:
            return int(rows[0][0])
        return 0
    except Exception as e:
        logger.error(f"[update-user-quota] activation_codes 累计充值查询失败: {e}, email={email}")
        return 0
    finally:
        db.disconnect()


def _quota_to_rmb(quota) -> float:
    """NewAPI 额度 → 人民币"""
    if not quota:
        return 0.0
    try:
        rate, _ = get_usd_cny_rate()
        return round(float(quota) / QUOTA_TO_USD * rate, 2)
    except Exception as e:
        logger.error(f"[update-user-quota] 汇率换算失败: {e}, quota={quota}")
        return 0.0


def get_user_info(username, email):
    """
    查询用户额度（人民币，只读）

    Returns:
        {
            "email": ...,
            "currency": "CNY",
            "balance": float,          # 剩余可用余额 ¥（unlimited 时为 0.0，看 unlimited 标志）
            "total_recharged": float,  # 累计充值 ¥
            "unlimited": bool,
            "has_key": bool,
        }
    """
    b = _server_b_balance(email)
    remain = b.get("remain_quota")
    unlimited = bool(b.get("unlimited"))
    has_key = bool(b.get("has_key"))

    # 剩余余额：unlimited 或拿不到 remain 时余额按 0，由 unlimited 标志区分
    if not unlimited and remain is not None:
        balance = _quota_to_rmb(remain)
    else:
        balance = 0.0

    total_recharged = _quota_to_rmb(_total_recharged_quota(email))

    result = {
        "email": email,
        "currency": "CNY",
        "balance": balance,
        "total_recharged": total_recharged,
        "unlimited": unlimited,
        "has_key": has_key,
    }
    logger.info(f"[update-user-quota] result email={email} → {result}")
    return result
