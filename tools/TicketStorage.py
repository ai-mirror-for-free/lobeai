"""工单附件存储：落盘、类型/大小校验、短时效签名下载 URL

为什么用签名 URL 而不是 Header 鉴权：
    <img src> 带不了 Authorization 头，工单详情里要直接渲染截图缩略图。
    签名 URL（HMAC + 过期时间）既能让 <img> 直接拉取，又不会产生永久裸链。
    签名密钥从 ENCRYPTION_KEY 派生，不新增密钥文件。

磁盘布局（attachment_dir 相对 lobeai 项目根，默认 data/tickets）：
    data/tickets/<ticket_id>/<uuid>.<ext>
原文件名只存数据库（ticket_attachments.file_name），不参与磁盘路径，避免穿越/中文/重名问题。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
import uuid
from pathlib import Path

from tools.ConfigManager import get_config, get_env

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 白名单：故意不含 svg / html / js / exe —— 图片站内渲染，svg 可执行脚本，必须挡掉
ALLOWED_EXTS = {
    "png", "jpg", "jpeg", "gif", "webp",
    "pdf", "txt", "log", "json", "md", "csv", "zip",
}
IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}

_SAFE_NAME = re.compile(r"[^\w.\-()\u4e00-\u9fff ]+")


class StorageError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def base_dir() -> Path:
    raw = get_config("tickets.attachment_dir", "data/tickets")
    path = Path(raw)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path


def max_file_bytes() -> int:
    return int(get_config("tickets.max_file_mb", 10) or 10) * 1024 * 1024


def max_message_bytes() -> int:
    return int(get_config("tickets.max_message_total_mb", 30) or 30) * 1024 * 1024


def max_files_per_message() -> int:
    return int(get_config("tickets.max_files_per_message", 6) or 6)


def clean_file_name(name: str) -> str:
    """只用于展示/落库，不用于磁盘路径。"""
    name = (name or "").replace("\\", "/").split("/")[-1].strip()
    name = _SAFE_NAME.sub("_", name)
    return (name or "file")[:200]


def ext_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def validate(name: str, size: int, mime: str | None) -> tuple[str, bool]:
    """返回 (ext, is_image)。不合法抛 StorageError。"""
    ext = ext_of(name)
    if not ext:
        raise StorageError("附件缺少扩展名，无法识别文件类型")
    if ext not in ALLOWED_EXTS:
        raise StorageError(
            f"不支持的附件类型 .{ext}（支持：{'/'.join(sorted(ALLOWED_EXTS))}）"
        )
    if size <= 0:
        raise StorageError("附件内容为空")
    if size > max_file_bytes():
        raise StorageError(f"单个附件不能超过 {max_file_bytes() // (1024 * 1024)}MB")
    if ext in ("jpg", "jpeg", "png", "gif", "webp") and mime and not mime.startswith("image/"):
        # 客户端 MIME 不可全信，但明显不符时先拦一层
        raise StorageError("图片类型与文件内容不匹配")
    return ext, ext in IMAGE_EXTS


def save(ticket_id: int, data: bytes, name: str) -> str:
    """落盘并返回相对路径（存 storage_path）。"""
    ext, _ = validate(name, len(data), None)
    folder = base_dir() / str(int(ticket_id))
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"{int(ticket_id)}/{uuid.uuid4().hex}.{ext}"
    (base_dir() / rel).write_bytes(data)
    return rel


def delete(rel_path: str | None) -> bool:
    """删除文件，返回是否真的删了（用于维护脚本统计）。"""
    if not rel_path:
        return False
    root = base_dir().resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)  # 目录穿越保护
    except ValueError:
        return False
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def resolve_download(rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    root = base_dir().resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target if target.is_file() else None


# ─── 签名 URL ────────────────────────────────────────────────────────

def _secret() -> bytes:
    raw = get_env("ENCRYPTION_KEY", "") or get_env("SECRET_KEY", "")
    return hashlib.sha256(f"{raw}|ticket-attach".encode("utf-8")).digest()


def _sign(attachment_id: int, exp: int) -> str:
    msg = f"{int(attachment_id)}:{int(exp)}".encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:40]


def signed_url(attachment_id: int) -> str:
    ttl_hours = int(get_config("tickets.attachment_url_ttl_hours", 24) or 24)
    exp = int(time.time()) + ttl_hours * 3600
    return f"/api/ticket-attachments/{int(attachment_id)}?exp={exp}&sig={_sign(attachment_id, exp)}"


def verify_signature(attachment_id: int, exp: int, sig: str) -> bool:
    if not sig:
        return False
    if int(exp) < int(time.time()):
        return False
    return hmac.compare_digest(_sign(attachment_id, exp), sig)


def guess_media_type(storage_path: str) -> str:
    ext = ext_of(storage_path)
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "log": "text/plain; charset=utf-8",
        "json": "application/json",
        "md": "text/markdown; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "zip": "application/zip",
    }.get(ext, "application/octet-stream")


def ensure_dirs() -> None:
    base_dir().mkdir(parents=True, exist_ok=True)


def _unused() -> None:  # pragma: no cover - 保留 os 依赖引用，避免 lint 误报
    os.getcwd()
