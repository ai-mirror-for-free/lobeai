"""
额度查询服务
根据用户 token (sk-xxx) 查询剩余人民币余额
"""
from tools.DbScript import NewApiDatabaseManager
from tools.GetNewestRate import get_usd_cny_rate
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file="quota_query.log")


def query_quota(token_key: str) -> dict:
    """
    根据 token key 查询人民币余额

    Args:
        token_key: 用户令牌 (sk-xxx)

    Returns:
        {"status": True, "balance": "10.00", "unlimited": False}
    """
    if not token_key or len(token_key) < 10:
        return {"status": False, "error": "无效的 token 格式"}

    db = NewApiDatabaseManager()
    try:
        db.connect()
        if not db.conn:
            return {"status": False, "error": "数据库连接失败"}

        result = db.execute_query(
            "SELECT remain_quota, unlimited_quota, name, status "
            "FROM tokens WHERE key = %s",
            (token_key,)
        )
        db.disconnect()

        if not result:
            return {"status": False, "error": "未找到该 token"}

        row = result[0]
        remain_quota = row[0]
        unlimited = row[1]

        # 检查状态
        status_code = row[3]
        if status_code == 2:
            return {"status": False, "error": "该 token 已被禁用"}
        if status_code == 3:
            return {"status": False, "error": "该 token 已过期"}

        if unlimited:
            return {"status": True, "balance": "无限制", "unlimited": True}

        # 获取汇率，将额度转为人民币
        rate, _ = get_usd_cny_rate()
        balance_rmb = remain_quota / 500000 * rate

        return {
            "status": True,
            "balance": f"{balance_rmb:.2f}",
            "balance_raw": round(balance_rmb, 2),
            "unlimited": False,
        }

    except Exception as e:
        logger.error(f"查询额度失败: {e}")
        return {"status": False, "error": f"查询失败: {str(e)}"}
    finally:
        try:
            db.disconnect()
        except:
            pass
