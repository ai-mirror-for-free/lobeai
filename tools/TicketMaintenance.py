"""工单定时维护：自动关单 + 过期附件清理

两个动作（顺序执行，互不依赖）：

1) 自动关单（只处理 replied 状态）
   条件：status='replied'
         AND last_admin_at < NOW() - auto_close_days
         AND (last_user_at IS NULL OR last_user_at <= last_admin_at)
   含义：管理员最后回复后 N 天，用户既没回来也没追问 → 关单。
   **open 状态永不自动关闭**（用户已确认：管理员没处理就一直挂着，提醒管理员）。

2) 附件清理（按关单时间）
   条件：attachment.status='active'
         AND ticket.closed_at IS NOT NULL
         AND ticket.closed_at < NOW() - retention_days
   动作：删物理文件 → storage_path=NULL, status='purged', purged_at=NOW()
   文字内容一律不动；已清理的附件行保留（前端显示"已过期清理"）。

用法（cron）：
    python tools/TicketMaintenance.py            # 真跑
    python tools/TicketMaintenance.py --dry-run  # 只打印统计，不删不改
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ConfigManager import get_config  # noqa: E402
from tools.LoggerManager import LoggerManager  # noqa: E402
from tools.TicketDb import ticket_cursor  # noqa: E402
from tools.TicketStorage import delete as delete_file  # noqa: E402

logger = LoggerManager(log_file="ticket_maintenance.log")


def auto_close(dry_run: bool = False) -> list[dict]:
    days = int(get_config("tickets.auto_close_days", 7) or 7)
    with ticket_cursor() as cur:
        cur.execute(
            """
            SELECT id, ticket_no, user_email, last_admin_at
              FROM ticket.tickets
             WHERE status = 'replied'
               AND last_admin_at IS NOT NULL
               AND last_admin_at < NOW() - (%s || ' days')::interval
               AND (last_user_at IS NULL OR last_user_at <= last_admin_at)
             ORDER BY last_admin_at
            """,
            (str(days),),
        )
        rows = cur.fetchall()

    if dry_run or not rows:
        return [dict(r) for r in rows]

    ids = [r["id"] for r in rows]
    with ticket_cursor() as cur:
        cur.execute(
            """UPDATE ticket.tickets
                  SET status = 'closed', closed_at = NOW(), close_reason = 'auto_7d'
                WHERE id = ANY(%s)""",
            (ids,),
        )
    logger.info(f"[maintenance] 自动关单 {len(ids)} 条: {[r['ticket_no'] for r in rows]}")
    return [dict(r) for r in rows]


def purge_attachments(dry_run: bool = False) -> dict:
    days = int(get_config("tickets.retention_days", 30) or 30)
    with ticket_cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.storage_path, a.file_name, t.ticket_no, t.closed_at
              FROM ticket.ticket_attachments a
              JOIN ticket.tickets t ON t.id = a.ticket_id
             WHERE a.status = 'active'
               AND t.closed_at IS NOT NULL
               AND t.closed_at < NOW() - (%s || ' days')::interval
             ORDER BY a.id
            """,
            (str(days),),
        )
        rows = cur.fetchall()

    deleted = 0
    if not dry_run:
        for row in rows:
            if delete_file(row["storage_path"]):
                deleted += 1
            with ticket_cursor() as cur:
                cur.execute(
                    """UPDATE ticket.ticket_attachments
                          SET status = 'purged', purged_at = NOW(), storage_path = NULL
                        WHERE id = %s""",
                    (row["id"],),
                )
        if rows:
            logger.info(
                f"[maintenance] 清理附件 {len(rows)} 个（文件实删 {deleted} 个）"
            )

    return {
        "matched": len(rows),
        "files_deleted": deleted,
        "tickets": sorted({r["ticket_no"] for r in rows}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="工单维护：自动关单 + 过期附件清理")
    parser.add_argument("--dry-run", action="store_true", help="只统计不修改")
    args = parser.parse_args()

    closed = auto_close(dry_run=args.dry_run)
    purged = purge_attachments(dry_run=args.dry_run)

    print(f"auto_close: {len(closed)} 条")
    for r in closed[:20]:
        print(f"  - {r['ticket_no']} {r['user_email']} last_admin_at={r['last_admin_at']}")
    print(
        f"purge_attachments: matched={purged['matched']} "
        f"files_deleted={purged['files_deleted']}"
    )
    if args.dry_run:
        print("(dry-run：未修改任何数据)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
