"""工单鉴权：用户侧走门户 token 校验，管理侧复用 lobeai 管理员 token

用户侧为什么不能「前端传 email 就信」：
    门户现有接口（/api/invite/info、/api/update-user-quota）都是传 email 即认，
    但工单里有截图、报错、账号信息，照抄那套等于任何人伪造 email 就能看别人工单。
    因此这里强制拿 Authorization: Bearer <门户 access token> 去问 claude_agent
    `/api/v1/auth/me`，以它返回的 email 为准（只做鉴权，不碰聊天链路）。

管理侧：复用 `/api/admin/login` 签发的 lobeai token（tools/AdminTokenManager），
    不新建 new-api 会话（与 TavilyKeyAdmin 同款做法）。

缓存：token -> email 结果缓存 60s，避免每次点开列表都多打一次 /me。
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

import requests

from tools.AdminTokenManager import verify_token
from tools.ConfigManager import get_config
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file="ticket.log")

_USER_CACHE_TTL = 60  # 秒


class TicketAuthError(Exception):
    """带 HTTP 状态码的鉴权/参数错误，路由层直接转 JSON 响应。"""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class UserCtx:
    email: str
    username: str = ""


_user_cache: dict[str, tuple[float, UserCtx]] = {}
_user_lock = threading.Lock()


def _bearer(authorization: str) -> str:
    auth = (authorization or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def resolve_user(authorization: str) -> UserCtx:
    """校验门户 access token，返回当前用户（email 小写）。

    抛 TicketAuthError：
      401 未登录 / 登录过期
      502 登录校验服务返回异常
      503 登录校验服务不可用（claude_agent 挂了）
    """
    token = _bearer(authorization)
    if not token:
        raise TicketAuthError("请先登录后再使用反馈功能")

    key = _cache_key(token)
    now = time.time()
    with _user_lock:
        hit = _user_cache.get(key)
    if hit and now - hit[0] < _USER_CACHE_TTL:
        return hit[1]

    base = (get_config("claude_agent.url") or "http://127.0.0.1:8000").rstrip("/")
    try:
        resp = requests.get(
            f"{base}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=6,
        )
    except requests.RequestException as e:
        logger.error(f"[ticket-auth] /auth/me 不可用: {e}")
        raise TicketAuthError("登录校验服务暂不可用，请稍后重试", 503) from e

    if resp.status_code in (401, 403):
        raise TicketAuthError("登录已过期，请重新登录")
    if resp.status_code != 200:
        logger.error(f"[ticket-auth] /auth/me 返回 {resp.status_code}: {resp.text[:200]}")
        raise TicketAuthError("登录校验失败，请稍后重试", 502)

    data = resp.json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise TicketAuthError("账号缺少邮箱信息，请联系管理员", 403)

    ctx = UserCtx(
        email=email,
        username=(data.get("display_name") or data.get("username") or "").strip(),
    )
    with _user_lock:
        _user_cache[key] = (now, ctx)
        # 顺手清掉过期项，避免长期运行内存膨胀
        if len(_user_cache) > 2000:
            for k, (ts, _) in list(_user_cache.items()):
                if now - ts >= _USER_CACHE_TTL:
                    _user_cache.pop(k, None)
    return ctx


def require_admin(authorization: str) -> dict:
    token = _bearer(authorization)
    entry = verify_token(token) if token else None
    if not entry:
        raise TicketAuthError("管理员登录已过期，请重新登录")
    return entry


def invalidate_token(token: str) -> None:
    """用户登出/改密后主动失效缓存（当前未接，预留）。"""
    with _user_lock:
        _user_cache.pop(_cache_key(token), None)
