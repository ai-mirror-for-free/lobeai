"""用户端工单业务（门户 /feedback 页面）

所有入口都要求 UserCtx（来自 tools.TicketAuth.resolve_user，即门户 access token 校验结果），
**不接受前端传 email**。

多轮规则（与后台一致）：
    open     用户刚建单 / 用户追评后 → 管理员待处理
    replied  管理员已回复 → 等用户回应
    closed   用户手动关 / 管理员关 / 管理员回复后 7 天用户无回应（auto_7d）
    关闭后用户再发消息 → 自动 reopen（reopened_count+1）
"""
from __future__ import annotations

import re
from datetime import datetime

from tools.ConfigManager import get_config
from tools.LoggerManager import LoggerManager
from tools.TicketDb import ticket_cursor
from tools.TicketNotifier import notify_new_ticket, notify_user_reply
from tools.TicketStorage import (
    StorageError,
    max_message_bytes,
    max_files_per_message,
    save as save_attachment,
    signed_url,
    validate as validate_attachment,
)

logger = LoggerManager(log_file="ticket.log")

CATEGORIES = ("cannot_use", "account", "billing", "feature", "other")
CATEGORY_LABELS = {
    "cannot_use": "无法使用",
    "account": "账号登录",
    "billing": "充值与额度",
    "feature": "功能建议",
    "other": "其他",
}
STATUS_LABELS = {"open": "待处理", "replied": "已回复", "closed": "已关闭"}

# 联系邮箱校验（不追求 RFC 完备，只挡明显错误）
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
MAX_ACTIVATION_CODE = 1000

MAX_SUBJECT = 200
MAX_CONTENT = 5000
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class TicketError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ─── 小工具 ──────────────────────────────────────────────────────────

def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone().isoformat(timespec="seconds")
    return str(dt)


def allowed_emails() -> set[str]:
    raw = get_config("tickets.allowed_emails", []) or []
    return {str(e).strip().lower() for e in raw if str(e).strip()}


def is_enabled() -> bool:
    return bool(get_config("tickets.enabled", False))


def is_allowed(email: str) -> bool:
    return email.strip().lower() in allowed_emails()


def require_allowed(email: str) -> None:
    if not is_enabled():
        raise TicketError("反馈功能暂未开放", 403)
    if not is_allowed(email):
        raise TicketError("反馈功能当前为内测，暂未对你的账号开放", 403)


def _int(value, default: int, low: int, high: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, v))


def _fetch_owned(cur, email: str, ticket_id: int, for_update: bool = False) -> dict:
    """取用户自己的工单。

    不存在 -> 404；已被用户移除 -> **410**（不是 404）。
    原因：lobeai 的 ProtectionMiddleware 把任何 404 当成扫描行为，直接封该 IP 1 小时。
    用户点开自己已移除的工单是正常行为，绝不能用 404。
    """
    sql = "SELECT * FROM ticket.tickets WHERE id = %s AND user_email = %s"
    if for_update:
        sql += " FOR UPDATE"
    cur.execute(sql, (ticket_id, email))
    row = cur.fetchone()
    if not row:
        raise TicketError("工单不存在", 404)
    if row.get("user_deleted_at"):
        raise TicketError("该工单已被你撤销并删除", 410)
    return row


def _ticket_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "ticket_no": row["ticket_no"],
        "category": row["category"],
        "category_label": CATEGORY_LABELS.get(row["category"], row["category"]),
        "subject": row["subject"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "user_unread": row.get("user_unread", 0),
        "last_message_at": _iso(row.get("last_message_at")),
        "created_at": _iso(row.get("created_at")),
        "closed_at": _iso(row.get("closed_at")),
        "close_reason": row.get("close_reason"),
        "reopened_count": row.get("reopened_count", 0),
    }


def _attachment_row(row: dict) -> dict:
    purged = row["status"] == "purged"
    return {
        "id": row["id"],
        "file_name": row["file_name"],
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes") or 0,
        "is_image": bool(row.get("is_image")),
        "status": row["status"],
        "url": None if purged else signed_url(row["id"]),
        "created_at": _iso(row.get("created_at")),
    }


# ─── 入口信息（灰度判定 + 未读红点）──────────────────────────────────

def entry_info(email: str) -> dict:
    """前端据此决定是否显示反馈入口。非白名单也返回 200，只是 enabled=False。"""
    if not is_enabled() or not is_allowed(email):
        return {"enabled": False, "unread": 0, "email": email}
    with ticket_cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(user_unread), 0) AS unread FROM ticket.tickets WHERE user_email = %s",
            (email,),
        )
        unread = int(cur.fetchone()["unread"] or 0)
    return {"enabled": True, "unread": unread, "email": email}


# ─── 列表 ────────────────────────────────────────────────────────────

def list_tickets(email: str, page=1, size=DEFAULT_PAGE_SIZE) -> dict:
    page = _int(page, 1, 1, 10000)
    size = _int(size, DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    offset = (page - 1) * size
    with ticket_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) AS total FROM ticket.tickets
                WHERE user_email = %s AND user_deleted_at IS NULL""",
            (email,),
        )
        total = int(cur.fetchone()["total"] or 0)
        cur.execute(
            """
            SELECT t.*,
                   (SELECT m.content FROM ticket.ticket_messages m
                     WHERE m.ticket_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_content,
                   (SELECT COUNT(*) FROM ticket.ticket_messages m
                     WHERE m.ticket_id = t.id) AS message_count,
                   (SELECT COUNT(*) FROM ticket.ticket_attachments a
                     WHERE a.ticket_id = t.id AND a.status = 'active') AS attachment_count
              FROM ticket.tickets t
             WHERE t.user_email = %s AND t.user_deleted_at IS NULL
             ORDER BY t.last_message_at DESC
             LIMIT %s OFFSET %s
            """,
            (email, size, offset),
        )
        rows = cur.fetchall()
    items = []
    for row in rows:
        item = _ticket_row(row)
        item["last_content"] = (row.get("last_content") or "")[:120]
        item["message_count"] = int(row.get("message_count") or 0)
        item["attachment_count"] = int(row.get("attachment_count") or 0)
        items.append(item)
    return {"items": items, "total": total, "page": page, "size": size}


# ─── 详情 ────────────────────────────────────────────────────────────

def get_ticket(email: str, ticket_id: int) -> dict:
    with ticket_cursor() as cur:
        row = _fetch_owned(cur, email, ticket_id)

        # 打开即视为已读
        if (row.get("user_unread") or 0) > 0:
            cur.execute(
                "UPDATE ticket.tickets SET user_unread = 0 WHERE id = %s", (ticket_id,)
            )

        cur.execute(
            "SELECT * FROM ticket.ticket_messages WHERE ticket_id = %s ORDER BY id",
            (ticket_id,),
        )
        message_rows = cur.fetchall()

        cur.execute(
            "SELECT * FROM ticket.ticket_attachments WHERE ticket_id = %s ORDER BY id",
            (ticket_id,),
        )
        attachment_rows = cur.fetchall()

    by_message: dict[int, list] = {}
    for a in attachment_rows:
        by_message.setdefault(a["message_id"], []).append(_attachment_row(a))

    ticket = _ticket_row(row)
    ticket["user_unread"] = 0
    messages = [
        {
            "id": m["id"],
            "author_role": m["author_role"],
            "content": m["content"] or "",
            "created_at": _iso(m.get("created_at")),
            "attachments": by_message.get(m["id"], []),
        }
        for m in message_rows
    ]
    return {"ticket": ticket, "messages": messages}


# ─── 新建 ────────────────────────────────────────────────────────────

def _rate_limit(email: str) -> None:
    limit = int(get_config("tickets.rate_limit_per_hour", 5) or 5)
    with ticket_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) AS n FROM ticket.tickets
                WHERE user_email = %s AND created_at > NOW() - INTERVAL '1 hour'""",
            (email,),
        )
        if int(cur.fetchone()["n"] or 0) >= limit:
            raise TicketError(f"提交过于频繁（每小时最多 {limit} 条），请稍后再试", 429)


def _prepare_files(files: list[tuple[str, str | None, bytes]]) -> list[dict]:
    if not files:
        return []
    if len(files) > max_files_per_message():
        raise TicketError(f"单条消息最多 {max_files_per_message()} 个附件")
    total = 0
    prepared = []
    for name, mime, data in files:
        try:
            ext, is_image = validate_attachment(name or "file", len(data), mime)
        except StorageError as e:
            raise TicketError(e.message, e.status_code) from e
        total += len(data)
        if total > max_message_bytes():
            raise TicketError(
                f"单条消息附件总大小不能超过 {max_message_bytes() // (1024 * 1024)}MB"
            )
        prepared.append({"name": name or "file", "mime": mime, "data": data, "is_image": is_image})
    return prepared


def _save_attachments(cur, ticket_id: int, message_id: int, role: str,
                      prepared: list[dict]) -> None:
    for item in prepared:
        try:
            rel = save_attachment(ticket_id, item["data"], item["name"])
        except StorageError as e:
            raise TicketError(e.message, e.status_code) from e
        cur.execute(
            """INSERT INTO ticket.ticket_attachments
                   (ticket_id, message_id, uploader_role, file_name, mime_type,
                    size_bytes, storage_path, is_image)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                ticket_id, message_id, role, item["name"][:255],
                (item["mime"] or "")[:128], len(item["data"]), rel, item["is_image"],
            ),
        )


def create_ticket(email: str, username: str, category: str, subject: str,
                  content: str, files: list[tuple[str, str | None, bytes]],
                  contact_email: str = "", activation_code: str = "") -> dict:
    require_allowed(email)

    category = (category or "other").strip()
    if category not in CATEGORIES:
        raise TicketError("请选择有效的反馈分类")
    subject = (subject or "").strip()
    content = (content or "").strip()
    if not subject:
        raise TicketError("请填写标题")
    if len(subject) > MAX_SUBJECT:
        raise TicketError(f"标题不能超过 {MAX_SUBJECT} 字")
    if not content:
        raise TicketError("请填写问题描述")
    if len(content) > MAX_CONTENT:
        raise TicketError(f"描述不能超过 {MAX_CONTENT} 字")

    # 联系邮箱：用户自己填，必填（登录账号邮箱只用于鉴权，不一定能联系到人）
    contact_email = (contact_email or "").strip().lower()
    if not contact_email:
        raise TicketError("请填写联系邮箱")
    if len(contact_email) > 254 or not EMAIL_RE.match(contact_email):
        raise TicketError("联系邮箱格式不正确")

    # 激活码：仅「充值与额度」类保存，其它分类一律存空（避免出现在无关工单里）
    if category == "billing":
        activation_code = (activation_code or "").strip()[:MAX_ACTIVATION_CODE]
    else:
        activation_code = ""

    prepared = _prepare_files(files)
    _rate_limit(email)

    with ticket_cursor() as cur:
        cur.execute(
            """INSERT INTO ticket.tickets
                   (user_email, user_name, category, subject, status,
                    contact_email, activation_code,
                    last_user_at, last_message_at, admin_unread)
               VALUES (%s, %s, %s, %s, 'open', %s, %s, NOW(), NOW(), 1)
               RETURNING id, ticket_no, status""",
            (email, (username or "")[:100], category, subject,
             contact_email, activation_code or None),
        )
        created = cur.fetchone()
        ticket_id = created["id"]

        cur.execute(
            """INSERT INTO ticket.ticket_messages (ticket_id, author_role, author_email, content)
               VALUES (%s, 'user', %s, %s) RETURNING id""",
            (ticket_id, email, content),
        )
        message_id = cur.fetchone()["id"]
        _save_attachments(cur, ticket_id, message_id, "user", prepared)

    logger.info(f"[ticket] 新建 {created['ticket_no']} email={email} files={len(prepared)}")
    notify_new_ticket(
        {
            "ticket_no": created["ticket_no"],
            "user_email": email,
            "contact_email": contact_email,
            "category": category,
            "subject": subject,
        },
        content,
    )
    return {
        "id": ticket_id,
        "ticket_no": created["ticket_no"],
        "status": "open",
        "attachment_count": len(prepared),
    }


# ─── 追评（多轮）─────────────────────────────────────────────────────

def add_message(email: str, ticket_id: int, content: str,
                files: list[tuple[str, str | None, bytes]]) -> dict:
    require_allowed(email)
    content = (content or "").strip()
    if not content and not files:
        raise TicketError("请输入内容或上传附件")
    if len(content) > MAX_CONTENT:
        raise TicketError(f"内容不能超过 {MAX_CONTENT} 字")
    prepared = _prepare_files(files)

    with ticket_cursor() as cur:
        row = _fetch_owned(cur, email, ticket_id, for_update=True)

        reopened = row["status"] == "closed"
        if reopened:
            cur.execute(
                """UPDATE ticket.tickets
                      SET status = 'open', closed_at = NULL, close_reason = NULL,
                          reopened_count = reopened_count + 1
                    WHERE id = %s""",
                (ticket_id,),
            )
        elif row["status"] != "open":
            cur.execute(
                "UPDATE ticket.tickets SET status = 'open' WHERE id = %s", (ticket_id,)
            )

        cur.execute(
            """INSERT INTO ticket.ticket_messages (ticket_id, author_role, author_email, content)
               VALUES (%s, 'user', %s, %s) RETURNING id""",
            (ticket_id, email, content),
        )
        message_id = cur.fetchone()["id"]
        _save_attachments(cur, ticket_id, message_id, "user", prepared)

        cur.execute(
            """UPDATE ticket.tickets
                  SET last_user_at = NOW(), last_message_at = NOW(),
                      admin_unread = admin_unread + 1
                WHERE id = %s""",
            (ticket_id,),
        )

    logger.info(
        f"[ticket] 用户追评 {row['ticket_no']} email={email} "
        f"files={len(prepared)} reopened={reopened}"
    )
    notify_user_reply(
        {"ticket_no": row["ticket_no"], "user_email": email},
        content,
        len(prepared),
        reopened,
    )
    return {
        "id": ticket_id,
        "ticket_no": row["ticket_no"],
        "status": "open",
        "reopened": reopened,
        "attachment_count": len(prepared),
    }


# ─── 关闭 ────────────────────────────────────────────────────────────

def close_ticket(email: str, ticket_id: int) -> dict:
    require_allowed(email)
    with ticket_cursor() as cur:
        row = _fetch_owned(cur, email, ticket_id, for_update=True)
        if row["status"] == "closed":
            return {"id": ticket_id, "status": "closed", "already": True}
        cur.execute(
            """UPDATE ticket.tickets
                  SET status = 'closed', closed_at = NOW(), close_reason = 'user'
                WHERE id = %s""",
            (ticket_id,),
        )
    logger.info(f"[ticket] 用户关闭 {row['ticket_no']} email={email}")
    return {"id": ticket_id, "status": "closed", "already": False}


# ─── 用户撤销并删除（软标记：只对自己隐藏，管理员可见）────────────

def delete_ticket(email: str, ticket_id: int) -> dict:
    """用户把工单从「我的工单」移除（撤销+删除合并后的唯一操作）。

    行为：打 user_deleted_at 时间戳 → 用户侧列表/详情/追评立即不可见，
    管理员后台仍能看到该工单并标记「用户已移除」。
    """
    require_allowed(email)
    with ticket_cursor() as cur:
        # 先确认归属与可见性：已移除的工单给 410（不能 404，否则封 IP）
        row = _fetch_owned(cur, email, ticket_id, for_update=True)
        cur.execute(
            "UPDATE ticket.tickets SET user_deleted_at = NOW() WHERE id = %s",
            (ticket_id,),
        )
    logger.info(f"[ticket] 用户撤销并删除 {row['ticket_no']} email={email}")
    return {"id": ticket_id, "ticket_no": row["ticket_no"], "action": "撤销并删除"}


# ─── 附件下载元信息 ──────────────────────────────────────────────────

def attachment_for_download(attachment_id: int) -> dict:
    """签名 URL 已被 HMAC 校验过（路由层），这里只取元数据。"""
    with ticket_cursor() as cur:
        cur.execute(
            "SELECT * FROM ticket.ticket_attachments WHERE id = %s", (attachment_id,)
        )
        row = cur.fetchone()
    if not row:
        raise TicketError("附件不存在", 404)
    if row["status"] == "purged" or not row["storage_path"]:
        raise TicketError("该附件已超过保留期并清理，仅保留文字记录", 410)
    return row
