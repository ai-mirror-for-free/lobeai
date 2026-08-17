"""共享管理员会话（全局单例）

lobeai 所有管理员操作复用同一个 new-api 登录会话，避免每次登录签发新会话
触发 new-api 的 AUTH_SESSION_LIMIT / AUTH_SESSION_ISSUANCE_LIMIT。

access_token 有效期 15 分钟，距上次刷新超过 12 分钟自动 refresh；
refresh 失败（如会话被撤销）fallback 重新 login。

进程每次重启会新建一条 active session（历史遗留无法自动过期回收），
因此登录成功后立即 revoke-others 清理旧会话，保证 A 端 new-api 上
管理员活跃会话恒为 1。
"""
import logging
import threading
import time

import requests

from services.NewAPIClient import NewAPIClient

logger = logging.getLogger("lobeai.shared_admin_session")

REFRESH_INTERVAL = 720  # 秒，access_token 15min 过期，12min 余量
RATE_LIMIT_COOLDOWN = 900  # 秒，new-api 返回 429 后本地冷却，不再反复尝试

_lock = threading.Lock()
_client: NewAPIClient | None = None
_last_refresh: float = 0.0
_rate_limited_until: float = 0.0  # monotonic 截止时间，期间不再尝试 refresh/login


def _do_login() -> NewAPIClient:
    client = NewAPIClient()
    try:
        client.login()  # login() 内部读 NEWAPI_USER + NEWAPI_PASSWORD_ENCRYPTED
    except requests.HTTPError as e:
        # 429 = 登录限流配额打满（CriticalRateLimit 按来源 IP 全局共享，
        # claude_agent 用户登录与 lobeai 共用同一桶）。立即进入本地冷却，
        # 避免后续每个管理请求都打两发 429 进一步拖长恢复时间。
        if e.response is not None and e.response.status_code == 429:
            global _rate_limited_until
            _rate_limited_until = time.monotonic() + RATE_LIMIT_COOLDOWN
            logger.error(f"管理员登录被限流(429)，本地冷却 {RATE_LIMIT_COOLDOWN}s")
        raise
    # 登录成功后撤销该管理员的历史登录会话（POST /api/user/sessions/revoke-others，
    # 带 access_token 即 revoke 其他 session），保证 A 端 new-api 上管理员活跃
    # 会话恒为 1 —— 否则每次进程重启都会遗留一条 active session 直至 50 上限。
    try:
        client.revoke_other_sessions()
    except Exception as e:
        logger.warning(f"管理员历史会话清理失败: {e}")
    return client


def get_admin_client() -> NewAPIClient:
    """返回全局共享的已认证管理员客户端（保证 access_token 未过期）"""
    global _client, _last_refresh
    now = time.monotonic()

    if _client is not None and (now - _last_refresh) < REFRESH_INTERVAL:
        return _client

    with _lock:
        now = time.monotonic()
        if _client is not None and (now - _last_refresh) < REFRESH_INTERVAL:
            return _client

        # 429 冷却期内直接失败，不再尝试 refresh/login（避免每请求刷两发 429）
        if now < _rate_limited_until:
            raise RuntimeError("管理员会话暂不可用: new-api 登录限流冷却中，请稍后再试")

        if _client is None:
            try:
                _client = _do_login()
            except Exception as e:
                raise RuntimeError(f"管理员会话初始化失败: {e}") from e
        else:
            # 已有会话：先尝试 refresh，失败则重新登录
            if not _client.refresh_login():
                try:
                    _client = _do_login()
                except Exception as e:
                    raise RuntimeError(f"管理员会话刷新失败: {e}") from e
        _last_refresh = time.monotonic()
    return _client
