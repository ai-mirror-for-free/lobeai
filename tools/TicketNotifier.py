"""gotify 通知：新工单 / 用户追问时推给管理员

约定：
- 只在 tickets.enabled 且 gotify.enabled 且有 token 时生效；任何失败只写日志，**绝不阻断建单/留言**。
- 发送放在 daemon 线程里，避免 gotify 慢/挂掉拖慢接口响应。
- token 在 config.yaml 里以**密文**存放（ENCRYPTION_KEY 加密，见 tools/password_encryption.py），不落明文。
- 强度：单个 app 就够，强调程度由消息 priority 决定（0 静音级 / 5 正常 / 10 高强调）。

gotify HTTP API：POST {url}/message
    header: X-Gotify-Key: <app token>
    body:   {"title": "...", "message": "...", "priority": 5}
"""
from __future__ import annotations

import threading
import time

import requests

from tools.ConfigManager import get_config, get_env
from tools.LoggerManager import LoggerManager
from tools.password_encryption import decrypt_password, get_decrypted_password

logger = LoggerManager(log_file="ticket.log")

# 强调程度 → gotify priority
PRIORITY = {
    "low": 0,       # 静音级：维护汇总、纯建议
    "normal": 5,    # 正常：影响使用、用户追问
    "high": 10,     # 高强调：涉钱、用户催办
}

CATEGORY_LABELS = {
    "cannot_use": "无法使用",
    "account": "账号登录",
    "billing": "充值与额度",
    "feature": "功能建议",
    "other": "其他",
}

# 分类 → 强调程度（充值涉钱用 high，影响使用用 normal，纯建议 low）
CATEGORY_LEVELS = {
    "billing": "high",
    "cannot_use": "normal",
    "account": "normal",
    "feature": "low",
    "other": "low",
}

_TOKEN_CACHE: dict = {}


def _token() -> str:
    """取 app token（先解 config 里的密文，再退回 .env 兼容方式）。"""
    raw = get_config("gotify.app_token", "") or ""
    if raw and _TOKEN_CACHE.get("raw") == raw:
        return _TOKEN_CACHE.get("token", "")
    token = ""
    if raw:
        try:
            token = decrypt_password(raw)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[gotify] app_token 解密失败: {e}")
    if not token:
        # 老部署兼容：.env 里的密文 / 明文
        try:
            token = get_decrypted_password("GOTIFY_APP_TOKEN_ENCRYPTED")
        except Exception:  # noqa: BLE001
            token = get_env("GOTIFY_APP_TOKEN", "") or ""
    _TOKEN_CACHE["raw"] = raw
    _TOKEN_CACHE["token"] = token
    return token


def _client_token(name: str = "") -> str:
    """取接收端 client token（只读消息，用于自检回读）。"""
    clients = get_config("gotify.clients", {}) or {}
    if not isinstance(clients, dict) or not clients:
        return ""
    raw = clients.get(name) if name else next(iter(clients.values()))
    if not raw:
        return ""
    try:
        return decrypt_password(raw)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[gotify] client token 解密失败: {e}")
        return ""


def enabled() -> bool:
    return bool(get_config("tickets.enabled", True)) and bool(get_config("gotify.enabled", False))


def _base_url() -> str:
    return (get_config("gotify.url") or "http://127.0.0.1:25800").rstrip("/")


def _send(title: str, message: str, level: str = "normal") -> None:
    if not enabled():
        return
    token = _token()
    if not token:
        logger.error("[gotify] 未配置 gotify.app_token，跳过推送")
        return
    priority = PRIORITY.get(level, PRIORITY["normal"])
    payload = {"title": title, "message": message, "priority": priority}
    last_err = ""
    # 重试一次：推送走公网时首次 DNS/TLS 握手可能拖到超时（生产用 127.0.0.1 不会有这问题）
    for attempt in (1, 2):
        try:
            resp = requests.post(
                f"{_base_url()}/message",
                headers={"X-Gotify-Key": token},
                json=payload,
                timeout=(6, 12),
            )
            if resp.status_code >= 300:
                last_err = f"{resp.status_code}: {resp.text[:200]}"
            else:
                return
        except requests.RequestException as e:
            last_err = str(e)
        if attempt == 1:
            time.sleep(1)
    logger.error(f"[gotify] 推送失败（已重试）: {last_err}")


def _send_async(title: str, message: str, level: str = "normal") -> None:
    threading.Thread(target=_send, args=(title, message, level), daemon=True).start()


def _trim(text: str, limit: int = 200) -> str:
    text = (text or "").replace("\r", "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _admin_url() -> str:
    return get_config("gotify.admin_ticket_url", "") or ""


def notify_new_ticket(ticket: dict, content: str) -> None:
    category = ticket.get("category", "") or ""
    label = CATEGORY_LABELS.get(category, category)
    lines = [
        f"单号：{ticket.get('ticket_no')}",
        f"用户：{ticket.get('user_email')}",
    ]
    contact = (ticket.get("contact_email") or "").strip()
    if contact and contact != (ticket.get("user_email") or ""):
        lines.append(f"联系邮箱：{contact}")
    lines += [
        f"分类：{label}",
        f"标题：{ticket.get('subject')}",
        f"内容：{_trim(content)}",
    ]
    msg = "\n".join(lines)
    link = _admin_url()
    if link:
        msg += f"\n\n处理入口：{link}"
    _send_async(
        f"【新工单】{ticket.get('ticket_no')} · {label}",
        msg,
        CATEGORY_LEVELS.get(category, "normal"),
    )


def notify_user_reply(
    ticket: dict, content: str, attachment_count: int = 0, reopened: bool = False
) -> None:
    msg = (
        f"单号：{ticket.get('ticket_no')}\n"
        f"用户：{ticket.get('user_email')}\n"
        f"内容：{_trim(content)}"
    )
    if attachment_count:
        msg += f"\n附件：{attachment_count} 个"
    if reopened:
        msg += "\n（已关单后用户重新追问，工单已重开）"
    link = _admin_url()
    if link:
        msg += f"\n\n处理入口：{link}"
    _send_async(
        f"【用户追问】{ticket.get('ticket_no')}",
        msg,
        "high" if reopened else "normal",
    )
