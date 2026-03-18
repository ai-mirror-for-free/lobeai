import requests
import sys
from tools.LoggerManager import LoggerManager
API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

logger = LoggerManager(log_file="rate.log")
def get_usd_cny_rate():
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rate = data["rates"]["CNY"]
        return rate

    except KeyError as e:
        logger.error(f"获取汇率失败 - 响应格式错误：{e}")
        logger.error(f"实际响应：{data}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"获取汇率失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    rate = get_usd_cny_rate()
    print(f"当前 USD -> CNY 汇率: {rate}")