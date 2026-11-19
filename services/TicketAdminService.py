"""管理端工单业务（home-admin「用户反馈」页）

与用户端共享同一套表与状态机：
    open → replied（管理员回复）→ closed（管理员关闭 / 用户关闭 / 7 天无回应自动关）
管理员对已关闭工单回复 → 自动重开为 replied（reopened_count+1）
"""
from __future__ import annotations

from datetime import datetime

from tools.LoggerManager import LoggerManager
from tools.TicketDb import ticket_cursor
from tools.TicketStorage import StorageError
from tools.TicketStorage import delete as delete_attachment_file
from tools.TicketStorage import save as save_attachment
from tools.TicketStorage import signed_url

from services.TicketService import (
    CATEGORY_LABELS,
    MAX_CONTENT,
    STATUS_LABELS,
    TicketError,
    _prepare_files,
    _int,
)

logger = LoggerManager(log_file="ticket.log")

ADMIN_PAGE_SIZE = 20


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone().isoformat(timespec="seconds")
    return str(dt)


def _row_to_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "ticket_no": row["ticket_no"],
        "user_email": row["user_email"],
        "user_name": row.get("user_name") or "",
        "contact_email": row.get("contact_email") or "",
        "activation_code": row.get("activation_code") or "",
        "category": row["category"],
        "category_label": CATEGORY_LABELS.get(row["category"], row["category"]),
        "subject": row["subject"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "admin_unread": row.get("admin_unread", 0),
        "user_unread": row.get("user_unread", 0),
        "last_content": (row.get("last_content") or "")[:160],
        "message_count": int(row.get("message_count") or 0),
        "attachment_count": int(row.get("attachment_count") or 0),
        "last_message_at": _iso(row.get("last_message_at")),
        "last_user_at": _iso(row.get("last_user_at")),
        "last_admin_at": _iso(row.get("last_admin_at")),
        "created_at": _iso(row.get("created_at")),
        "closed_at": _iso(row.get("closed_at")),
        "close_reason": row.get("close_reason"),
        "reopened_count": row.get("reopened_count", 0),
        # 用户侧移除标记：管理员仍可见
        "user_deleted_at": _iso(row.get("user_deleted_at")),
        "user_hidden": bool(row.get("user_deleted_at")),
    }


def list_tickets(keyword: str = "", status: str = "", category: str = "",
                 only_unread: bool = False, page=1, size=ADMIN_PAGE_SIZE) -> dict:
    page = _int(page, 1, 1, 100000)
    size = _int(size, ADMIN_PAGE_SIZE, 1, 100)
    offset = (page - 1) * size

    where = []
    params: list = []
    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        where.append(
            """(t.ticket_no ILIKE %s OR t.user_email ILIKE %s OR t.subject ILIKE %s
                OR t.contact_email ILIKE %s OR t.activation_code ILIKE %s
                OR EXISTS (SELECT 1 FROM ticket.ticket_messages m
                            WHERE m.ticket_id = t.id AND m.content ILIKE %s))"""
        )
        params.extend([like, like, like, like, like, like])
    if status in ("open", "replied", "closed"):
        where.append("t.status = %s")
        params.append(status)
    if category in CATEGORY_LABELS:
        where.append("t.category = %s")
        params.append(category)
    if only_unread:
        where.append("t.admin_unread > 0")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with ticket_cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS total FROM ticket.tickets t {where_sql}", params
        )
        total = int(cur.fetchone()["total"] or 0)

        cur.execute(
            f"""
            SELECT t.*,
                   (SELECT m.content FROM ticket.ticket_messages m
                     WHERE m.ticket_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_content,
                   (SELECT COUNT(*) FROM ticket.ticket_messages m
                     WHERE m.ticket_id = t.id) AS message_count,
                   (SELECT COUNT(*) FROM ticket.ticket_attachments a
                     WHERE a.ticket_id = t.id AND a.status = 'active') AS attachment_count
              FROM ticket.tickets t
              {where_sql}
             ORDER BY (t.admin_unread > 0) DESC, t.last_message_at DESC
             LIMIT %s OFFSET %s
            """,
            params + [size, offset],
        )
        rows = cur.fetchall()

    return {
        "items": [_row_to_item(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }


def get_ticket(ticket_id: int) -> dict:
    with ticket_cursor() as cur:
        cur.execute("SELECT * FROM ticket.tickets WHERE id = %s", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise TicketError("工单不存在", 404)

        if (row.get("admin_unread") or 0) > 0:
            cur.execute(
                "UPDATE ticket.tickets SET admin_unread = 0 WHERE id = %s", (ticket_id,)
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
        purged = a["status"] == "purged"
        by_message.setdefault(a["message_id"], []).append({
            "id": a["id"],
            "file_name": a["file_name"],
            "mime_type": a.get("mime_type"),
            "size_bytes": a.get("size_bytes") or 0,
            "is_image": bool(a.get("is_image")),
            "status": a["status"],
            "url": None if purged else signed_url(a["id"]),
            "created_at": _iso(a.get("created_at")),
        })

    ticket = _row_to_item(row)
    ticket["admin_unread"] = 0
    messages = [
        {
            "id": m["id"],
            "author_role": m["author_role"],
            "author_email": m.get("author_email") or "",
            "content": m["content"] or "",
            "created_at": _iso(m.get("created_at")),
            "attachments": by_message.get(m["id"], []),
        }
        for m in message_rows
    ]
    return {"ticket": ticket, "messages": messages}


def reply(ticket_id: int, content: str, files: list[tuple[str, str | None, bytes]],
          operator: str) -> dict:
    content = (content or "").strip()
    if not content and not files:
        raise TicketError("请输入回复内容或上传附件")
    if len(content) > MAX_CONTENT:
        raise TicketError(f"回复内容不能超过 {MAX_CONTENT} 字")
    prepared = _prepare_files(files)

    with ticket_cursor() as cur:
        cur.execute(
            "SELECT * FROM ticket.tickets WHERE id = %s FOR UPDATE", (ticket_id,)
        )
        row = cur.fetchone()
        if not row:
            raise TicketError("工单不存在", 404)

        reopened = row["status"] == "closed"
        if reopened:
            cur.execute(
                """UPDATE ticket.tickets
                      SET status = 'replied', closed_at = NULL, close_reason = NULL,
                          reopened_count = reopened_count + 1
                    WHERE id = %s""",
                (ticket_id,),
            )
        else:
            cur.execute(
                "UPDATE ticket.tickets SET status = 'replied' WHERE id = %s", (ticket_id,)
            )

        cur.execute(
            """INSERT INTO ticket.ticket_messages (ticket_id, author_role, author_email, content)
               VALUES (%s, 'admin', %s, %s) RETURNING id""",
            (ticket_id, operator, content),
        )
        message_id = cur.fetchone()["id"]

        for item in prepared:
            try:
                rel = save_attachment(ticket_id, item["data"], item["name"])
            except StorageError as e:
                raise TicketError(e.message, e.status_code) from e
            cur.execute(
                """INSERT INTO ticket.ticket_attachments
                       (ticket_id, message_id, uploader_role, file_name, mime_type,
                        size_bytes, storage_path, is_image)
                   VALUES (%s, %s, 'admin', %s, %s, %s, %s, %s)""",
                (
                    ticket_id, message_id, item["name"][:255],
                    (item["mime"] or "")[:128], len(item["data"]), rel, item["is_image"],
                ),
            )

        cur.execute(
            """UPDATE ticket.tickets
                  SET last_admin_at = NOW(), last_message_at = NOW(),
                      user_unread = user_unread + 1
                WHERE id = %s""",
            (ticket_id,),
        )

    logger.info(
        f"[ticket-admin] 回复 {row['ticket_no']} operator={operator} "
        f"files={len(prepared)} reopened={reopened}"
    )
    return {
        "id": ticket_id,
        "ticket_no": row["ticket_no"],
        "status": "replied",
        "reopened": reopened,
        "attachment_count": len(prepared),
    }


def set_status(ticket_id: int, status: str, operator: str) -> dict:
    if status not in ("open", "replied", "closed"):
        raise TicketError("无效的状态")
    with ticket_cursor() as cur:
        cur.execute(
            "SELECT * FROM ticket.tickets WHERE id = %s FOR UPDATE", (ticket_id,)
        )
        row = cur.fetchone()
        if not row:
            raise TicketError("工单不存在", 404)

        if status == "closed":
            cur.execute(
                """UPDATE ticket.tickets
                      SET status = 'closed', closed_at = NOW(), close_reason = 'admin'
                    WHERE id = %s""",
                (ticket_id,),
            )
        else:
            cur.execute(
                """UPDATE ticket.tickets
                      SET status = %s, closed_at = NULL, close_reason = NULL
                    WHERE id = %s""",
                (status, ticket_id),
            )
    logger.info(f"[ticket-admin] 状态变更 {row['ticket_no']} -> {status} operator={operator}")
    return {"id": ticket_id, "ticket_no": row["ticket_no"], "status": status}


def stats() -> dict:
    with ticket_cursor() as cur:
        cur.execute(
            """SELECT
                   COUNT(*) FILTER (WHERE status = 'open')     AS open_count,
                   COUNT(*) FILTER (WHERE status = 'replied')  AS replied_count,
                   COUNT(*) FILTER (WHERE status = 'closed')   AS closed_count,
                   COUNT(*) FILTER (WHERE admin_unread > 0)    AS unread_count,
                   COUNT(*) FILTER (WHERE user_deleted_at IS NOT NULL) AS hidden_count,
                   COUNT(*)                                    AS total_count
                 FROM ticket.tickets"""
        )
        row = cur.fetchone()
    return {k: int(v or 0) for k, v in row.items()}


# ─── 硬删除 / 恢复 ────────────────────────────────────────────────

def hard_delete(ticket_ids: list[int], operator: str) -> dict:
    """管理员彻底删除：真删库 + 删物理附件，不可恢复。

    按外键从下往上删：attachments → messages → tickets。
    文件先删（行删了就拿不到 storage_path 了），文件不存在不影响删行。
    """
    ids = [int(i) for i in (ticket_ids or []) if str(i).strip().lstrip("-").isdigit()]
    if not ids:
        raise TicketError("请选择要删除的工单")
    if len(ids) > 200:
        raise TicketError("单次最多删除 200 条")

    removed_files = 0
    deleted_nos: list[str] = []

    with ticket_cursor() as cur:
        cur.execute(
            "SELECT id, ticket_no FROM ticket.tickets WHERE id = ANY(%s)", (ids,)
        )
        rows = {r["id"]: r["ticket_no"] for r in cur.fetchall()}
        if not rows:
            raise TicketError("工单不存在", 404)

        cur.execute(
            "SELECT storage_path FROM ticket.ticket_attachments WHERE ticket_id = ANY(%s)",
            (list(rows),),
        )
        paths = [r["storage_path"] for r in cur.fetchall() if r.get("storage_path")]
        for rel in paths:
            try:
                if delete_attachment_file(rel):
                    removed_files += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[ticket-admin] 删除附件文件失败 {rel}: {e}")

        cur.execute(
            "DELETE FROM ticket.ticket_attachments WHERE ticket_id = ANY(%s)", (list(rows),)
        )
        cur.execute(
            "DELETE FROM ticket.ticket_messages WHERE ticket_id = ANY(%s)", (list(rows),)
        )
        cur.execute("DELETE FROM ticket.tickets WHERE id = ANY(%s)", (list(rows),))
        deleted_nos = list(rows.values())

    logger.info(
        f"[ticket-admin] 硬删 {len(deleted_nos)} 条 operator={operator} "
        f"files={removed_files} nos={','.join(deleted_nos[:10])}"
    )
    return {
        "deleted": len(deleted_nos),
        "files_removed": removed_files,
        "ticket_nos": deleted_nos,
    }

