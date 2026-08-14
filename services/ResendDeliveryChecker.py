"""
Resend 投递状态检查器

new-api 的 /api/verification 同步接受 SMTP 投递即返回成功（200），
邮箱是否真实存在（硬退信 550）是 Resend 异步投递后才反馈的。
本模块在验证码发送后轮询 Resend 投递状态，识别硬退信邮箱并缓存，
供 send-verification-code 接口提示用户"邮箱不存在"。

Resend API key 读取顺序：环境变量 RESEND_API_KEY > A 端 new-api
oneapi 库 options 表 SMTPToken（避免明文散落）。
"""
import json
import os
import time
from pathlib import Path

import requests

from tools.DbScript import NewApiDatabaseManager

_RESEND_API = "https://api.resend.com/emails"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BOUNCE_CACHE = _DATA_DIR / "bounced_emails.json"
_WAIT_SECONDS = 4.0  # 发送后等待投递判定（硬退信通常秒级-几十秒反馈）


def get_resend_api_key() -> str:
    """获取 Resend API key：env 优先，其次 new-api oneapi 库 options 表 SMTPToken"""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if api_key:
        return api_key
    try:
        db = NewApiDatabaseManager()
        rows = db.execute_query(
            "SELECT value FROM options WHERE key = 'SMTPToken' LIMIT 1"
        )
        if rows and rows[0] and rows[0][0]:
            return rows[0][0]
    except Exception:
        pass
    return ""


def load_bounced() -> dict:
    """读取退信邮箱缓存 {email: timestamp}"""
    if not _BOUNCE_CACHE.exists():
        return {}
    try:
        return json.loads(_BOUNCE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_bounced(bounced: dict) -> None:
    try:
        _BOUNCE_CACHE.write_text(
            json.dumps(bounced, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def is_known_bounced(email: str) -> bool:
    """发送前检查：该邮箱此前是否已确认硬退信"""
    return email.lower() in load_bounced()


def mark_bounced(email: str) -> None:
    """记录硬退信邮箱（含时间戳）"""
    bounced = load_bounced()
    bounced[email.lower()] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_bounced(bounced)


def check_email_delivery(email: str, wait_seconds: float = _WAIT_SECONDS) -> str:
    """发送后轮询 Resend 最新投递状态

    Args:
        email: 收件邮箱
        wait_seconds: 等待 Resend 完成投递判定（硬退信通常秒级反馈）

    Returns:
        "bounced":   硬退信（邮箱不存在）
        "delivered": 已投递成功
        "unknown":   未能判定（投递延迟 / 接口异常，不阻塞正常流程）
    """
    api_key = get_resend_api_key()
    if not api_key:
        return "unknown"
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    try:
        # 注意：Resend /emails 的 to 参数不生效，返回全局最新列表，需遍历匹配
        resp = requests.get(
            _RESEND_API,
            params={"limit": 100},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return "unknown"
        data = resp.json()
        items = data.get("data") or []
        target = email.lower()
        # 匹配该邮箱最近一条投递记录
        latest = None
        for item in items:
            to_list = item.get("to") or []
            if target in [str(t).lower() for t in to_list]:
                latest = item
                break
        if latest is None:
            return "unknown"
        last_event = latest.get("last_event")
        if last_event == "bounced":
            return "bounced"
        if last_event == "delivered":
            return "delivered"
        return "unknown"
    except Exception:
        return "unknown"
