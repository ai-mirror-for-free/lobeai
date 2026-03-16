"""
本脚本为自动创建用户，并分配对应余额的月级别令牌
1. 使接收套餐级别作为入参
2. 创建用户, 使用services/sever_for_open_webui/register_users.py函数注册用户并返回payload
    payload = {"name": name, "email": email, "password": password}
3. 依据用户的套餐级别，调用new-api创建令牌
4. 更新 pg 库中用户信息

"""

# 创建用户
from tools.pricing_process import PRICING_PLAN
from tools.db_script import NewApiDatabaseManager,OpenWebUIDatabaseManager
from services.sever_for_open_webui.register_users import register_random_user
from services.server_for_new_api.create_token import NewAPIClient

newapidata = NewApiDatabaseManager()
openwebuidata = OpenWebUIDatabaseManager()
client = NewAPIClient()


def create_user(crash_type=None):
    assert crash_type in PRICING_PLAN.keys(), "请输入正确的 crashing_type"
    prcing_plan = PRICING_PLAN[crash_type]
    payload = register_random_user()
    

