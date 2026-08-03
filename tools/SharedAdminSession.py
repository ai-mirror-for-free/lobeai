"""共享管理员会话（全局单例）

lobeai 所有管理员操作复用同一个 new-api 登录会话，避免每次登录签发新会话
触发 new-api 的 AUTH_SESSION_LIMIT / AUTH_SESSION_ISSUANCE_LIMIT。

access_token 有效期 15 分钟，距上次刷新超过 12 分钟自动 refresh；
refresh 失败（如会话被撤销）fallback 重新 login。
"""
import threading
import time

from services.NewAPIClient import NewAPIClient

REFRESH_INTERVAL = 720  # 秒，access_token 15min 过期，12min 余量

_lock = threading.Lock()
_client: NewAPIClient | None = None
_last_refresh: float = 0.0


def _do_login() -> NewAPIClient:
    client = NewAPIClient()
    client.login()  # login() 内部读 NEWAPI_USER + NEWAPI_PASSWORD_ENCRYPTED
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
