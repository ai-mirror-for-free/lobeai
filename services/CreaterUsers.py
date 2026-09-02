"""
自动创建用户服务

1. 接收用户信息作为入参
2. 在 NewAPI 中注册用户账号
3. 在 users_center 表中初始化一行（plan_level="default"，仅作历史占位字段）。
   - 默认 / vip / svip 套餐已下线，本字段不再参与任何业务判断。
   - Claude Code 激活码由 server_b 侧独立委派处理，不在 users_center 写记录。

注意：当前服务不直接创建 NewAPI token，所有 key 一律通过激活码分配。
"""

import json
from datetime import datetime
from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager
from services.NewAPIClient import NewAPIClient

newapidata = NewApiDatabaseManager()
newapiclient = NewAPIClient()
logger = LoggerManager(log_file="user_manager.log")


def main_register_user(
    username: str, password: str, email: str, verification_code: str, aff_code=None
):
    # 邀请码前置校验（复用 new-api aff_code，邀请者必须已充值走 server_b 同口径）
    aff_code = (aff_code or "").strip() if isinstance(aff_code, str) else aff_code
    inviter = None
    if aff_code:
        try:
            from services.InviteService import validate_invite
            inviter, err = validate_invite(aff_code, email)
            if err:
                logger.warning(f"[invite] 注册拒绝 aff_code={aff_code} email={email} reason={err}")
                return {
                    "success": False,
                    "message": err,
                }
            # validate 通过则 inviter 非 None，无码则 inviter 为 None
        except Exception as e:
            logger.error(f"[invite] 校验异常 aff_code={aff_code} email={email}: {e}")
            return {
                "success": False,
                "message": f"邀请码校验失败: {e}",
            }

    # NewAPI 注册（仍透传 aff_code 让 new-api 写 inviter_id，原有逻辑不受影响）
    try:
        newapiclient.register(
            username, password, email, verification_code, aff_code
        )
        logger.info(f"新用户已创建: 用户名:{username}, 邮箱:{email}")
    except RuntimeError as e:
        logger.error(f"用户名已经存在: {e}, 请更换用户名")
        return {
            "success": False,
            "message": "用户名或邮箱已存在，请更换后重试",
        }

    # 检查是否为忘记密码恢复（users_center 中是否已有该邮箱记录）
    newapidata.connect()
    existing = newapidata.execute_query(
        "SELECT token, plan_level FROM users_center WHERE email = %s", (email,)
    )
    newapidata.disconnect()

    if existing:
        # 忘记密码恢复：仅复用已有记录，不重复插入
        logger.info(f"用户 {username} 为忘记密码恢复，复用已有记录: {email}")
        return {
            "success": True,
            "message": "密码已恢复，欢迎回来",
            "data": {
                "username": username,
                "password": password,
                "email": email,
            },
        }

    # 新用户：仅在 users_center 初始化一行
    # - plan_level = "default" （历史占位字段，套餐已下线，不再参与判断）
    # - quota_left / days_left / token 全部为 0/空，激活后由对应链路写入
    newapidata.connect()
    newapidata.execute_command(
        "INSERT INTO users_center (name, email, plan_level, plan_price, days_left, quota_left, recharge, token) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (username, email, "default", 0, 0, 0, 0, ""),
    )
    newapidata.disconnect()
    logger.info(
        f"用户 {username} 已在 users_center 初始化: plan_level=default (历史占位)"
    )

    # 邀请绑定落库（仅新用户且有有效邀请码时）
    if inviter and aff_code:
        try:
            from services.InviteService import create_binding
            # need invitee user id from new-api users
            invitee_uid = None
            try:
                qdb = NewApiDatabaseManager()
                qdb.connect()
                if qdb.conn:
                    with qdb.conn.cursor() as cur:
                        cur.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (email.strip().lower(),))
                        r = cur.fetchone()
                        if r:
                            invitee_uid = int(r[0])
                    qdb.disconnect()
            except Exception as e:
                logger.error(f"[invite] 查询 invitee uid 失败 {email}: {e}")
                try:
                    qdb.disconnect()
                except Exception:
                    pass
            if invitee_uid:
                ok, msg = create_binding(email, invitee_uid, inviter, aff_code)
                if not ok:
                    logger.warning(f"[invite] 绑定落库失败 email={email} aff={aff_code}: {msg}")
                else:
                    logger.info(f"[invite] 绑定落库成功 email={email} aff={aff_code}")
            else:
                logger.error(f"[invite] 未找到 invitee uid email={email} 无法绑定")
        except Exception as e:
            logger.error(f"[invite] 绑定异常 email={email}: {e}")

    return {
        "success": True,
        "message": "用户已创建成功, 请使用 Claude Code 激活码激活",
        "data": {
            "username": username,
            "password": password,
            "email": email,
            "verification_code": verification_code,
        },
    }
