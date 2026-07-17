"""
本脚本为自动创建用户
1. 接收用户信息作为入参
2. 分别在 newapi 和 openwebui 同步进行注册
3. 在 users_center 表中初始化一行（plan_level="default", quota=0），
   等用户用激活码激活时再由 buy_package 升级 plan_level
4. 【历史】曾在此脚本里为新用户创建 group="free" 的 NewAPI token 并送 50000 quota，
   现已删除——key 一律通过激活码分配，不在注册时创建。
"""

# 创建用户
import json
from datetime import datetime
from tools.LoggerManager import LoggerManager
from tools.Setting import get_setting
from func.PricingProcess import fill_pricing_plan
from tools.DbScript import NewApiDatabaseManager, OpenWebUIDatabaseManager
from services.OpenWebuiRegisterUsers import register_user
from services.NewAPIClient import NewAPIClient

newapidata = NewApiDatabaseManager()
openwebuidata = OpenWebUIDatabaseManager()
newapiclient = NewAPIClient()
logger = LoggerManager(log_file="user_manager.log")


def main_register_user(
    username: str, password: str, email: str, verification_code: str, aff_code=None
):

    # new api 注册（保留：用户需要 NewAPI 账号才能调用激活码兑换路径）
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

    PRICING_PLAN = fill_pricing_plan()

    # 检查是否为忘记密码恢复（users_center 中是否已有该邮箱记录）
    newapidata.connect()
    existing = newapidata.execute_query(
        "SELECT token, plan_level FROM users_center WHERE email = %s", (email,)
    )
    newapidata.disconnect()

    if existing:
        # 忘记密码恢复：复用已有令牌和套餐级别，只更新 OpenWebUI settings
        token_key, plan_level = existing[0]
        model_limits = PRICING_PLAN[plan_level]["modele_list"]
        logger.info(f"用户 {username} 为忘记密码恢复，复用已有令牌，套餐: {plan_level}")

        setting = get_setting(token_key, model_limits)
        setting = json.dumps(setting)
        openwebuidata.connect()
        openwebuidata.execute_command(
            'UPDATE "user" SET settings = %s WHERE email = %s', (setting, email)
        )
        openwebuidata.disconnect()

        logger.info(f"用户 {username} 密码恢复完成")
        return {
            "success": True,
            "message": "密码已恢复，欢迎回来",
            "data": {
                "username": username,
                "password": password,
                "email": email,
            },
        }

    # 新用户：仅在 users_center 初始化一行，不创建 NewAPI token
    # - plan_level = "default" （未激活状态, 由 buy_package 在激活时覆盖为具体套餐）
    # - quota_left = 0        （不再赠送初始额度, 一律通过激活码获取）
    # - days_left = 0         （未激活, 无过期时间）
    # - token = ""            （无 token, 等 buy_package 创建后由其 UPDATE 填入）
    newapidata.connect()
    newapidata.execute_command(
        "INSERT INTO users_center (name, email, plan_level, plan_price, days_left, quota_left, recharge, token) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (username, email, "default", 0, 0, 0, 0, ""),
    )
    newapidata.disconnect()
    logger.info(
        f"用户 {username} 已在 users_center 初始化: plan_level=default (待激活)"
    )
    return {
        "success": True,
        "message": "用户已创建成功, 请使用激活码激活套餐",
        "data": {
            "username": username,
            "password": password,
            "email": email,
            "verification_code": verification_code,
        },
    }