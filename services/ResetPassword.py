"""
忘记密码后重置账号服务

校验用户名+邮箱后，从 NewAPI 和 OpenWebUI 数据库中删除用户。
IP 限流：每小时 3 次失败尝试，超限封禁 1 天。
"""
import time
from collections import defaultdict
from fastapi import Request
from tools.DbScript import NewApiDatabaseManager, OpenWebUIDatabaseManager
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

    # 校验用户名和邮箱
    openwebui_db = OpenWebUIDatabaseManager()
    openwebui_db.connect()
    result = openwebui_db.execute_query(
        'SELECT id FROM "user" WHERE name = %s AND email = %s', (username, email)
    )
    openwebui_db.disconnect()

    if not result:
        ip_reset_attempts[ip].append(now)
        attempts_left = RESET_LIMIT - len(ip_reset_attempts[ip])

        if attempts_left <= 0:
            ip_reset_blocked[ip] = now
            ip_reset_attempts[ip].clear()
            logger.info(f"[BLOCKED] reset-password ip={ip} 失败次数超限，封禁 1 天")
            return {"message": "您已尝试次数过多，IP已被封禁1天"}

        logger.info(f"[FAILED] reset-password ip={ip} username={username} attempts_left={attempts_left}")
        return {"message": f"用户名或邮箱不正确，您还有 {attempts_left} 次尝试机会"}

    # 删除用户：NewAPI users 表
    newapi_db = NewApiDatabaseManager()
    newapi_db.connect()
    newapi_db.execute_command("DELETE FROM users WHERE email = %s AND role != 100", (email,))
    newapi_db.disconnect()

    # 删除用户：OpenWebUI user 表
    openwebui_db = OpenWebUIDatabaseManager()
    openwebui_db.connect()
    openwebui_db.execute_command('DELETE FROM "user" WHERE email = %s AND role != \'admin\'', (email,))
    openwebui_db.disconnect()

    # 成功后清除该 IP 的失败记录
    ip_reset_attempts.pop(ip, None)

    logger.info(f"用户 {username} 已通过密码重置接口删除")
    return {"message": "账号已重置，请尽快注册避免账号遗失"}
