import time
import json
from services.OpenWebuiAuth import get_jwt_token
from tools.LoggerManager import LoggerManager
from tools.PricingProcess import fill_pricing_plan
from tools.GetNewestRate import get_usd_cny_rate
from tools.DbScript import NewApiDatabaseManager, OpenWebUIDatabaseManager
from services.NewAPIClient import NewAPIClient, TokenConfig
from services.UpdateUserQuotaRequest import get_user_info


logger = LoggerManager(log_file="buy_package.log")
new_api_db = NewApiDatabaseManager()
newapiclient = NewAPIClient()
openwebuidata = OpenWebUIDatabaseManager()


def buy_package(
    username: str, email: str, password: str, plan_level: str, buy_mounth: int
):
    """
    1. 验证用户登录
    2. 登录错误返回用户账号密码错误
    3. 登录成功后，查询用户当前 套餐级别和剩余余额
    4. 依据用户套餐级别和余额,计算新的额度和模型列表，并调用 new api 创建新的 token
    5. 删除旧的 token
    5. 创建成功后，返回新的 token并复用到 setting
    """
    PRICING_PLAN = fill_pricing_plan()
    assert buy_mounth > 0, {"status": False, "message": f" 购买时长不能小于1个月"}
    assert plan_level in PRICING_PLAN, {"status": False, "message": f"套餐级别错误"}
    # 验证用户登录
    try:
        get_jwt_token(email, password)
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        return {"status": False, "message": f"用户登录失败: {e}"}
    # 获取用户信息
    user_info = get_user_info(username, email)
    if not user_info:
        logger.error("用户信息获取失败")
        return {"status": False, "message": "用户信息获取失败"}
    # 获取用户余额
    remain_quota = user_info["remain_quota"]
    # 获取用户套餐级别
    new_api_db.connect()
    sql = "select plan_level, token, days_left from users_center where email = %s and name = %s"
    plan_level_old, token_old, expired_time = new_api_db.execute_query(
        sql, (email, username)
    )[0]
    if plan_level_old == "free":
        logger.info("用户是免费用户")
        remain_quota = 0
        expired_time = int(time.time())
    # 计算新的额度和模型列表
    plan_info = PRICING_PLAN[plan_level]
    rate_result = get_usd_cny_rate()
    rate, local = rate_result  # 获取汇率值
    if not local:
        logger.error("获取汇率失败, 请检查网络")
    remain_quota += plan_info["price"] * buy_mounth / rate * 500000
    remain_quota = int(remain_quota / 100) * 100
    model_limits = plan_info["modele_list"]
    expired_time += buy_mounth * 30 * 86400
    # 创建新的 token 1. 过期时间为buy_mounth月 2. 模型列表为 model_limits. 3. 额度为 remain_quota
    newapiclient.login()
    trail_token = newapiclient.create_token(
        TokenConfig(
            name=email,
            remain_quota=remain_quota,
            expired_time=expired_time,
            unlimited_quota=False,
            model_limits_enabled=True,
            model_limits=",".join(model_limits),
        )
    )
    newapiclient.logout()
    token_key = trail_token.get("key")
    logger.info("用户新令牌已经创建")

    if not token_key or token_key == "***":
        logger.error(
            f"警告: 无法获取有效的 token key，token_id: {trail_token.get('id')}"
        )
        raise RuntimeError("无法获取有效的 token key")

    # 生成装配文件
    setting = {
        "ui": {
            "version": "0.8.10",
            "directConnections": {
                "OPENAI_API_BASE_URLS": ["https://filter.yang-sjq.cn/v1"],
                "OPENAI_API_KEYS": [token_key],
                "OPENAI_API_CONFIGS": {
                    "0": {
                        "enable": True,
                        "tags": [],
                        "prefix_id": "  ",
                        "model_ids": model_limits,
                        "connection_type": "external",
                        "auth_type": "bearer",
                    }
                },
            },
        }
    }
    # 更新 openwebui 用户设置
    setting = json.dumps(setting)
    update_settings = 'update "user" set settings = %s where email = %s'
    openwebuidata.connect()
    openwebuidata.execute_command(update_settings, (setting, email))

    # 更新用户中心
    sql = "update users_center set plan_level = %s, plan_price = %s, days_left = %s, quota_left = %s, token = %s where email = %s and name = %s"
    new_api_db.execute_command(
        sql,
        (
            plan_level,
            plan_info["price"],
            expired_time,
            remain_quota,
            token_key,
            email,
            username,
        ),
    )
    # 删除旧的 token
    sql = "delete from tokens where key = %s"
    new_api_db.execute_command(sql, (token_old,))
    openwebuidata.disconnect()
    new_api_db.disconnect()
    return {
        "status": True,
        "message": {
            "message": "购买成功",
            "plan_level": plan_level,
            "plan_price": plan_info["price"],
            "days_left": expired_time,
            "quota_left": remain_quota,
        },
    }


if __name__ == "__main__":
    print(buy_package("2277248178", "2277248178@qq.com", "yf3816547290", "pro", 2))
