import os
import json
import requests
from tools.LoggerManager import LoggerManager

API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
logger = LoggerManager(log_file="rate.log")

RATE_FILE = "data/usd_cny_rate.json"
os.makedirs("data", exist_ok=True)


def get_usd_cny_rate():
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rate = data["rates"]["CNY"]

        # 保存汇率到 data 文件夹
        with open(RATE_FILE, "w") as f:
            json.dump({"rate": rate}, f)

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