import requests
from tools.LoggerManager import LoggerManager

API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
logger = LoggerManager(log_file="rate.log")

def get_usd_cny_rate():
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rate = data["rates"]["CNY"]
        return rate, True

    except Exception as e:
        logger.error(f"获取汇率失败：{e}")
        return 6.9, False
