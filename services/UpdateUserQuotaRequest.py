from datetime import datetime
from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager

logger = LoggerManager()
db = NewApiDatabaseManager()


def get_user_info(username, email):
    """
    获取用户信息
    :param email:
    :return:
    """
    db.connect()
    sql = "select remain_quota,model_limits,used_quota,expired_time from tokens where name = %s and deleted_at is null"
    user_key_info = db.execute_query(sql, (email,))
    user_key_info = user_key_info[0]
    """
    remain_quota:剩余额度
    model_limits:模型限制
    used_quota:已使用额度
    expired_time:到期时间
    """
    user_key_info = {
        "remain_quota": user_key_info[0],
        "model_limits": user_key_info[1],
        "used_quota": user_key_info[2],
        "expired_time": user_key_info[3],
    }
    update_sql = "update users_center set days_left = %s,quota_left = %s where name = %s and email = %s"

    db.execute_command(
        update_sql,
        (
            user_key_info["expired_time"],
            user_key_info["remain_quota"],
            username,
            email,
        ),
    )


if __name__ == "__main__":
    get_user_info("", "测试")
