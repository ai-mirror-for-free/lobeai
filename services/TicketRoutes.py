"""工单 HTTP 路由（用户端 + 管理端）

挂载方式（main.py 末尾两行，与 TavilyKeyAdmin 一致）：
    from services.TicketRoutes import register_ticket_routes
    register_ticket_routes(app)

约定：
- 响应体统一 {"success": bool, "message": str, "data": ...}
- 同步 DB 调用一律 run_in_threadpool，避免堵 FastAPI 事件循环
  （lobeai 曾出现同步 DB 卡住导致整进程无响应的先例）
- 附件下载走 HMAC 签名 URL，不带 Authorization（<img> 需要）
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from services import TicketAdminService, TicketService
from services.TicketService import TicketError
from tools.LoggerManager import LoggerManager
from tools.TicketAuth import TicketAuthError, require_admin, resolve_user
from tools.TicketStorage import (
    guess_media_type,
    max_file_bytes,
    max_files_per_message,
    max_message_bytes,
    resolve_download,
    verify_signature,
)

logger = LoggerManager(log_file="ticket.log")

router = APIRouter(prefix="/api", tags=["tickets"])

MB = 1024 * 1024


# ─── 响应helper ──────────────────────────────────────────────────────

def _ok(data=None, message: str = "") -> dict:
    body = {"success": True}
    if message:
        body["message"] = message
    if data is not None:
        body["data"] = data
    return body


def _fail(err: Exception) -> JSONResponse:
    if isinstance(err, (TicketError, TicketAuthError)):
        return JSONResponse(
            status_code=err.status_code,
            content={"success": False, "message": err.message},
        )
    logger.error(f"[ticket] 未处理异常: {type(err).__name__}: {err}")
    return JSONResponse(
        status_code=500, content={"success": False, "message": "服务异常，请稍后重试"}
    )


def _auth_header(request: Request) -> str:
    return request.headers.get("Authorization", "")


async def _read_uploads(files: list[UploadFile] | None) -> list[tuple[str, str | None, bytes]]:
    """把 UploadFile 读成内存 bytes，并在读取阶段就做大小/数量限制。

    读取上限用 max_file_bytes()+1 探测超限，避免超大文件把内存吃满。
    """
    files = [f for f in (files or []) if f is not None and (f.filename or "")]
    if not files:
        return []
    if len(files) > max_files_per_message():
        raise TicketError(f"单条消息最多 {max_files_per_message()} 个附件")

    out: list[tuple[str, str | None, bytes]] = []
    total = 0
    for f in files:
        data = await f.read(max_file_bytes() + 1)
        if len(data) > max_file_bytes():
            raise TicketError(f"单个附件不能超过 {max_file_bytes() // MB}MB")
        total += len(data)
        if total > max_message_bytes():
            raise TicketError(f"单条消息附件总大小不能超过 {max_message_bytes() // MB}MB")
        out.append((f.filename or "file", f.content_type, data))
    return out


# ─── 用户端 ──────────────────────────────────────────────────────────

@router.get("/tickets/entry")
async def api_tickets_entry(request: Request):
    """灰度入口：{enabled, unread, email}；非白名单返回 200 + enabled=false。"""
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        data = await run_in_threadpool(TicketService.entry_info, ctx.email)
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.get("/tickets")
async def api_tickets_list(request: Request, page: int = 1, size: int = 20):
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        data = await run_in_threadpool(TicketService.list_tickets, ctx.email, page, size)
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/tickets")
async def api_tickets_create(
    request: Request,
    category: str = Form("other"),
    subject: str = Form(""),
    content: str = Form(""),
    contact_email: str = Form(""),
    activation_code: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        uploads = await _read_uploads(files)
        data = await run_in_threadpool(
            TicketService.create_ticket,
            ctx.email, ctx.username, category, subject, content, uploads,
            contact_email, activation_code,
        )
        return _ok(data, "提交成功，我们会尽快处理")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.get("/tickets/{ticket_id}")
async def api_tickets_detail(request: Request, ticket_id: int):
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        data = await run_in_threadpool(TicketService.get_ticket, ctx.email, ticket_id)
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/tickets/{ticket_id}/messages")
async def api_tickets_add_message(
    request: Request,
    ticket_id: int,
    content: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        uploads = await _read_uploads(files)
        data = await run_in_threadpool(
            TicketService.add_message, ctx.email, ticket_id, content, uploads
        )
        return _ok(data, "已发送")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/tickets/{ticket_id}/close")
async def api_tickets_close(request: Request, ticket_id: int):
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        data = await run_in_threadpool(TicketService.close_ticket, ctx.email, ticket_id)
        return _ok(data, "工单已关闭")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/tickets/{ticket_id}/delete")
async def api_tickets_delete(request: Request, ticket_id: int):
    """用户撤销并删除（撤销/删除合并为一个操作）：用户侧不可见，管理员仍可见。"""
    try:
        ctx = await run_in_threadpool(resolve_user, _auth_header(request))
        TicketService.require_allowed(ctx.email)
        data = await run_in_threadpool(TicketService.delete_ticket, ctx.email, ticket_id)
        return _ok(data, "已移除，该工单不再显示")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.get("/ticket-attachments/{attachment_id}")
async def api_ticket_attachment(attachment_id: int, exp: int = 0, sig: str = ""):
    """签名 URL 下载/预览（<img src> 可直接用）。"""
    try:
        if not verify_signature(attachment_id, exp, sig):
            raise TicketError("附件链接已失效，请刷新页面重试", 403)
        row = await run_in_threadpool(
            TicketService.attachment_for_download, attachment_id
        )
        path = resolve_download(row["storage_path"])
        if path is None:
            raise TicketError("附件文件不存在", 404)
        name = row["file_name"] or path.name
        media_type = row.get("mime_type") or guess_media_type(row["storage_path"])
        disposition = "inline" if row.get("is_image") else "attachment"
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(name)}",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=3600",
            },
        )
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


# ─── 管理端 ──────────────────────────────────────────────────────────

class AdminListReq(BaseModel):
    keyword: str = ""
    status: str = ""
    category: str = ""
    only_unread: bool = False
    page: int = 1
    size: int = 20


class AdminGetReq(BaseModel):
    ticket_id: int


class AdminStatusReq(BaseModel):
    ticket_id: int
    status: str


class AdminDeleteReq(BaseModel):
    ticket_ids: list[int] = []


@router.post("/admin/tickets/list")
async def api_admin_tickets_list(request: Request, payload: AdminListReq):
    try:
        await run_in_threadpool(require_admin, _auth_header(request))
        data = await run_in_threadpool(
            TicketAdminService.list_tickets,
            payload.keyword, payload.status, payload.category,
            payload.only_unread, payload.page, payload.size,
        )
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/get")
async def api_admin_tickets_get(request: Request, payload: AdminGetReq):
    try:
        await run_in_threadpool(require_admin, _auth_header(request))
        data = await run_in_threadpool(TicketAdminService.get_ticket, payload.ticket_id)
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/reply")
async def api_admin_tickets_reply(
    request: Request,
    ticket_id: int = Form(...),
    content: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    try:
        entry = await run_in_threadpool(require_admin, _auth_header(request))
        uploads = await _read_uploads(files)
        operator = (entry or {}).get("username") or "admin"
        data = await run_in_threadpool(
            TicketAdminService.reply, ticket_id, content, uploads, operator
        )
        return _ok(data, "回复已发送")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/status")
async def api_admin_tickets_status(request: Request, payload: AdminStatusReq):
    try:
        entry = await run_in_threadpool(require_admin, _auth_header(request))
        operator = (entry or {}).get("username") or "admin"
        data = await run_in_threadpool(
            TicketAdminService.set_status, payload.ticket_id, payload.status, operator
        )
        return _ok(data, "状态已更新")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/stats")
async def api_admin_tickets_stats(request: Request):
    try:
        await run_in_threadpool(require_admin, _auth_header(request))
        data = await run_in_threadpool(TicketAdminService.stats)
        return _ok(data)
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/delete")
async def api_admin_tickets_delete(request: Request, payload: AdminDeleteReq):
    """管理员硬删除：真删库（工单 + 消息 + 附件行 + 物理文件），不可恢复。"""
    try:
        entry = await run_in_threadpool(require_admin, _auth_header(request))
        operator = (entry or {}).get("username") or "admin"
        data = await run_in_threadpool(
            TicketAdminService.hard_delete, payload.ticket_ids, operator
        )
        return _ok(data, "已彻底删除")
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


@router.post("/admin/tickets/ping")
async def api_admin_tickets_ping(request: Request):
    """排障用：验证 DB 连接与三张表是否就绪。"""
    try:
        await run_in_threadpool(require_admin, _auth_header(request))
        from tools.TicketDb import ping as db_ping

        db = await run_in_threadpool(db_ping)
        stats = await run_in_threadpool(TicketAdminService.stats)
        return _ok({"db": db, "stats": stats})
    except (TicketError, TicketAuthError) as e:
        return _fail(e)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def register_ticket_routes(app) -> None:
    app.include_router(router)
    logger.info("[ticket] routes registered under /api/tickets & /api/admin/tickets")
