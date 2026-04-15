"""
本脚本为自动创建用户，并分配对应余额的月级别令牌
1. 接收套餐级别和用户信息作为入参
2. 分别在 newapi 和 openwebui 同步进行注册
3. 依据用户的套餐级别，调用new-api创建令牌
4. 更新 pg 库中用户信息

"""

# 创建用户
import json
import time
from datetime import datetime
from tools.GetNewestRate import get_usd_cny_rate
from tools.LoggerManager import LoggerManager
from tools.Setting import get_setting
from func.PricingProcess import fill_pricing_plan
from tools.DbScript import NewApiDatabaseManager, OpenWebUIDatabaseManager
from services.OpenWebuiRegisterUsers import register_user
from services.NewAPIClient import NewAPIClient, TokenConfig

newapidata = NewApiDatabaseManager()
openwebuidata = OpenWebUIDatabaseManager()
newapiclient = NewAPIClient()
logger = LoggerManager(log_file="user_manager.log")


def main_register_user(
    username: str, password: str, email: str, verification_code: str, aff_code=None
):

    # new api 注册
    try:
        newapiclient.register(
            username, password, email, verification_code, aff_code
        )
        logger.info(f"新用户已创建: 用户名:{username}, 邮箱:{email}")
    except RuntimeError as e:
        logger.error(f"用户名已经存在: {e}, 请更换用户名")
        return 

    # open webui 注册
    register_user(username, email, password)

    # 管理员登录（使用环境变量中的管理员账户）
    newapiclient.login()
    PRICING_PLAN = fill_pricing_plan()
    model_limits = PRICING_PLAN["free"]["modele_list"]
    expired_time = int(time.time()) + 86400
    # 创建免费试用令牌，1. 全模型可用 2. 额度50000 3。 1 天后过期
    trail_token = newapiclient.create_token(
        TokenConfig(
            name=email,
            remain_quota=50000,
            expired_time=expired_time,
            unlimited_quota=False,
            model_limits_enabled=True,
            model_limits=",".join(model_limits),
            group="free"
        )
    )

    # 获取完整的 token key
    # NewAPIClient.create_token 会从数据库获取完整的 key，而不是被屏蔽的 key
    token_key = trail_token.get("key")
    logger.info("限制令牌已创建")

    if not token_key or token_key == "***":
        logger.error(
            f"警告: 无法获取有效的 token key，token_id: {trail_token.get('id')}"
        )
        raise RuntimeError("无法获取有效的 token key")

    # 生成装配文件
    setting = get_setting(token_key, model_limits)
    # 查询 pg 库
    setting = json.dumps(setting)
    update_settings = 'update "user" set settings = %s where email = %s'
    openwebuidata.connect()
    openwebuidata.execute_command(update_settings, (setting, email))
    openwebuidata.disconnect()

    # 更新用户中心信息
    newapidata.connect()
    newapidata.execute_command(
        "insert into users_center (name, email, plan_level, plan_price, days_left, quota_left, recharge, token) values (%s, %s, %s, %s, %s, %s, %s, %s)",
        (username, email, "free", 0, expired_time, 50000, 0, token_key),
    )
    newapidata.disconnect()
    logger.info(f"用户信息已更新: {username}")
    return {
        "success": True,
        "message": "用户已创建成功",
        "data": {
            "username": username,
            "password": password,
            "email": email,
            "verification_code": verification_code,
        },
    }
