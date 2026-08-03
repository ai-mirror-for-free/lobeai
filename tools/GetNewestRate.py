import os
import json
import logging
import requests
from tools.DbScript import NewApiDatabaseManager
from tools.LoggerManager import LoggerManager

API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
logger = LoggerManager(log_file="rate.log")

RATE_FILE = "data/usd_cny_rate.json"
os.makedirs("data", exist_ok=True)


def _read_db_rate():
    """优先读 A 端 newapi 库 options.USDExchangeRate（统一汇率唯一权威来源）。

    每天凌晨 3 点由 server a scripts/orphan_cleanup.py 阶段 4 同步实时汇率
    到 A/B 两端库。读库失败/无值 → None（继续降级到 API / 文件）。
    """
    try:
        db = NewApiDatabaseManager()
        db.connect()
        if not db.conn:
            logger.warning("A 端 oneapi 库连接失败，回退 API")
            return None
        try:
            rows = db.execute_query(
                "SELECT value FROM options WHERE key = 'USDExchangeRate'"
            )
        finally:
            db.disconnect()
        if not rows:
            logger.warning("USDExchangeRate not set in A 端 options，回退 API")
            return None
        rate = float(rows[0][0])
        if rate <= 0:
            logger.warning(f"非法汇率: {rate}，回退 API")
            return None
        logger.info(f"使用 A 端库汇率: {rate}")
        return rate
    except Exception as e:
        logger.warning(f"读 A 端库汇率失败: {e}")
        return None


def _save_rate_file(rate):
    """写缓存文件（库不可用时的过渡兜底）。"""
    try:
        with open(RATE_FILE, "w") as f:
            json.dump({"rate": rate}, f)
    except Exception as e:
        logger.warning(f"写汇率缓存文件失败: {e}")


def get_usd_cny_rate():
    """统一汇率：A 端库 options.USDExchangeRate → 实时 API → 缓存文件。

    Returns:
        (rate, local)  local 恒为 True（有兜底值就算可用）
    """
    rate = _read_db_rate()
    if rate is not None:
        return rate, True

    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"]["CNY"]
        _save_rate_file(rate)
        return rate, True
    except Exception as e:
        logger.error(f"获取汇率失败：{e}")
        return _read_saved_rate()


def _read_saved_rate():
    if not os.path.exists(RATE_FILE):
        with open(RATE_FILE, "w") as f:
            json.dump({"rate": 6.8}, f)
    """读取保存的汇率文件"""
    with open(RATE_FILE, "r") as f:
        saved = json.load(f)
        rate = saved.get("rate")
        logger.info(f"使用保存的汇率：{rate}")
        return rate, True


if __name__ == "__main__":
    print(get_usd_cny_rate())
