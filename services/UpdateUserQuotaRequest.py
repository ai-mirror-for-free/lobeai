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
    if not user_key_info:
        # 新用户首次兑换：tokens 表无 name=email 行；
        # buy_package 后续会 create_token(name=email) 创建第一个 token，
        # 给个占位值让流程继续即可。expired_time 留 now+30d 让 max() 算得对。
        import time as _t
        user_key_info = [(0, "", 0, int(_t.time()) + 30 * 86400)]
        logger.warning(f"用户无 token 行（首次兑换?），使用占位值: email={email}")
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
    # email 是唯一判定键
    sql = "select plan_level, name from users_center where email = %s"
    rows = db.execute_query(sql, (email,))
    if not rows:
        logger.error(f"未找到 users_center 记录: email={email}")
        db.disconnect()
        return None
    plan_level, stored_name = rows[0]
    user_key_info["plan_level"] = plan_level

    # 如果用户名变了，同步到 users_center（email 是唯一判定，按 email 匹配）
    if stored_name != username:
        logger.info(
            f"users_center.name 变更: {stored_name} -> {username}, email={email}"
        )
        db.execute_command(
            "update users_center set name = %s where email = %s",
            (username, email),
        )

    # 更新用户中心 剩余时间，套餐余额
    update_sql = "update users_center set days_left = %s, quota_left = %s where email = %s"
    db.execute_command(
        update_sql,
        (
            user_key_info["expired_time"],
            user_key_info["remain_quota"],
            email,
        ),
    )
    db.disconnect()
    return user_key_info
