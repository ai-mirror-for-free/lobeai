"""
忘记密码后重置账号服务

校验用户名+邮箱后，从 NewAPI 数据库中删除用户。
IP 限流：每小时 3 次失败尝试，超限封禁 1 天。
"""
import time
from collections import defaultdict
from fastapi import Request
from tools.DbScript import NewApiDatabaseManager
from tools.LoggerManager import LoggerManager

# -- IP 限流配置 --
RESET_LIMIT = 3
RESET_WINDOW = 3600        # 1 小时窗口
RESET_BLOCK_SECONDS = 86400  # 封禁 1 天

ip_reset_attempts: dict[str, list[float]] = defaultdict(list)
ip_reset_blocked: dict[str, float] = {}

logger = LoggerManager(log_file="reset_password.log")


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset_password(username: str, email: str, req: Request) -> dict:
    ip = _get_client_ip(req)
    now = time.time()

    # 检查是否在被封禁期
    if ip in ip_reset_blocked:
        if now - ip_reset_blocked[ip] < RESET_BLOCK_SECONDS:
            remaining = int(RESET_BLOCK_SECONDS - (now - ip_reset_blocked[ip]))
            h, m = remaining // 3600, (remaining % 3600) // 60
            return {"message": f"您的IP已被限制访问，请在 {h} 小时 {m} 分钟后重试"}
        else:
            del ip_reset_blocked[ip]

    # 清理过期记录
    ip_reset_attempts[ip] = [t for t in ip_reset_attempts[ip] if now - t < RESET_WINDOW]

    # 校验用户名和邮箱（从 NewAPI users 表查询，排除管理员 role=100）
    # 匹配规则：
    #   - 邮箱：忽略大小写比较（lower）
    #   - 用户名：两侧各取前 4 个字符、忽略大小写比较；用户名不足 4 字符时
    #     等价于必须完整写对（用户输入多打字符即不通过）
    #   - 两侧先 btrim 去掉首尾空格
    # 全部走 psycopg2 参数化，防注入
    newapi_db = NewApiDatabaseManager()
    newapi_db.connect()
    result = newapi_db.execute_query(
        """
        SELECT id FROM users
        WHERE lower(email) = lower(%s) AND role != 100
          AND username IS NOT NULL AND username <> ''
          AND lower(left(btrim(username), 4)) = lower(left(btrim(%s), 4))
        """,
        (email, username),
    )

    if not result:
        newapi_db.disconnect()
        ip_reset_attempts[ip].append(now)
        attempts_left = RESET_LIMIT - len(ip_reset_attempts[ip])

        if attempts_left <= 0:
            ip_reset_blocked[ip] = now
            ip_reset_attempts[ip].clear()
            logger.info(f"[BLOCKED] reset-password ip={ip} 失败次数超限，封禁 1 天")
            return {"message": "您已尝试次数过多，IP已被封禁1天"}

        logger.info(f"[FAILED] reset-password ip={ip} username={username} attempts_left={attempts_left}")
        return {"message": f"用户名或邮箱不正确，您还有 {attempts_left} 次尝试机会"}

    # 校验通过：删除 NewAPI 用户（排除管理员）
    # 注意：email 匹配必须与上面的校验条件保持一致（同样忽略大小写），
    # 否则用户输入大写邮箱时会出现「校验通过但删不到人」的不一致
    newapi_db.execute_command(
        "DELETE FROM users WHERE lower(email) = lower(%s) AND role != 100", (email,)
    )
    newapi_db.disconnect()

    # 成功后清除该 IP 的失败记录
    ip_reset_attempts.pop(ip, None)

    logger.info(f"用户 {username} 已通过密码重置接口删除")
    return {"message": "账号已重置，请尽快注册避免账号遗失"}
