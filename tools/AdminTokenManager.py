"""lobeai 管理员本地 token 管理

对外 /api/admin/login 签发短期 token，对接方后续凭 token 调用管理员接口。
token 存进程内存，单进程部署足够（lobeai 以 python main.py 单进程运行）。
"""
import secrets
import time
import threading

TOKEN_TTL = 86400  # 24 小时

_lock = threading.Lock()
_tokens: dict[str, dict] = {}  # {token: {"username": str, "expires_at": int}}


def _now() -> int:
    return int(time.time())


def issue_token(username: str) -> str:
    """签发一个 token，返回 token 明文（调用方负责返回给对接方）"""
    token = secrets.token_urlsafe(32)
    with _lock:
        _tokens[token] = {"username": username, "expires_at": _now() + TOKEN_TTL}
    return token


def verify_token(token: str) -> dict | None:
    """校验 token。有效返回 {"username": ..., "expires_at": ...}，无效/过期返回 None。"""
    if not token:
        return None
    with _lock:
        entry = _tokens.get(token)
        if entry is None:
            return None
        if entry["expires_at"] <= _now():
            _tokens.pop(token, None)  # 惰性清理过期项
            return None
        return entry
