"""Tavily key 池管理（管理员界面用）— lobeai → server_b /tavily/*

背景（2026-10-18）
    Tavily key 池原在 B 端 server_b/config/config.yaml，改为入库管理：
    真源 = B 端 claude_rag.tavily_keys（DDL 见 docs/schema.sql 8c 段）。
    管理页（admin.chat-keeper.com）→ lobeai `/api/admin/tavily/*` → server_b `/tavily/*`。

设计要点（遵守「lobeai 小范围修改」原则：独立文件 + 一个注册函数）
- 本模块只做三件事：校验管理员 token、转发到 server_b、统一响应体
- 鉴权：复用 lobeai `/api/admin/login` 签发的 token（Bearer），不新建会话
- 到 server_b 的调用带 CF Service Token（Enforce JWT）+ `X-Admin-Token`
  （后者是 server_b 侧的 websearch.admin_token，配在 A 端 .env：
   `SERVER_B_TAVILY_ADMIN_TOKEN=...`）
- 不落任何 key 明文：server_b 只回显掩码
- server_b 的 /usage 探测是**按来源 IP 限速**的，所以「立即检测」单次只探一小批
  （B 端 `websearch.manual_check_max_keys`，默认 6 把），返回体含 deferred 提示

响应体统一：{"success": bool, "message": str, "data": ...}
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel

import requests

from tools.AdminTokenManager import verify_token
from tools.ConfigManager import get_env
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file="tavily_key_admin.log")

# 读接口 15s；/tavily/check 要逐把探测（B 端批内间隔 3s），给足 60s
TIMEOUT_READ = 15
TIMEOUT_CHECK = 60

ADMIN_TOKEN_ENV = "SERVER_B_TAVILY_ADMIN_TOKEN"


# ─── 入参模型 ────────────────────────────────────────────────────────────
class TavilyListRequest(BaseModel):
    include_disabled: bool = True


class TavilyAddRequest(BaseModel):
    keys: list[str] = []      # 多行粘贴（前端按行拆分）
    key: str = ""             # 单个
    label: str = ""


class TavilyKeyIdRequest(BaseModel):
    id: int


class TavilySetEnabledRequest(BaseModel):
    id: int
    enabled: bool = True
    reason: str = "manual"


class TavilyCheckRequest(BaseModel):
    ids: list[int] = []
    force: bool = False


# ─── 内部工具 ────────────────────────────────────────────────────────────
def _require_admin(req: Request) -> str:
    """校验管理员 Bearer token，返回操作者名；无效直接 401（前端会跳登录）。"""
    auth = req.headers.get("Authorization", "")
    token = auth[len("Bearer "):].strip() if auth.startswith("Bearer ") else ""
    entry = verify_token(token) if token else None
    if not entry:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return entry.get("username") or "admin"


def _server_b_headers() -> dict:
    """调 server_b 的认证头：CF Service Token + X-Admin-Token。"""
    from services.ClaudeCodeActivation import _cf_access_headers

    headers = dict(_cf_access_headers())
    admin_token = get_env(ADMIN_TOKEN_ENV, "") or ""
    if not admin_token:
        raise RuntimeError(f"未配置 {ADMIN_TOKEN_ENV}，无法调用 server_b 管理接口")
    headers["X-Admin-Token"] = admin_token
    return headers


def _call(method: str, path: str, *, params: dict | None = None, body: dict | None = None,
          timeout: int = TIMEOUT_READ) -> dict:
    """转发到 server_b 并归一化响应体。"""
    from services.ClaudeCodeActivation import _server_b_url

    url = _server_b_url() + path
    try:
        resp = requests.request(
            method, url, params=params, json=body,
            headers=_server_b_headers(), timeout=timeout,
        )
    except Exception as e:
        logger.error(f"[tavily] server_b 调用失败: {method} {path} {type(e).__name__}: {e}")
        return {"success": False, "message": f"server_b 不可达: {e}"}

    if resp.status_code == 401:
        logger.error(f"[tavily] server_b 管理接口鉴权失败（检查 {ADMIN_TOKEN_ENV} 是否与 B 端一致）")
        return {"success": False, "message": "server_b 管理接口鉴权失败（ADMIN_TOKEN 不一致）"}
    if resp.status_code == 503:
        return {"success": False, "message": _detail(resp) or "server_b 管理接口未启用"}
    try:
        data = resp.json()
    except Exception:
        logger.error(f"[tavily] server_b 返回非 JSON: {method} {path} status={resp.status_code}")
        return {"success": False, "message": f"server_b 返回异常（HTTP {resp.status_code}）"}

    if not resp.ok:
        logger.warning(f"[tavily] server_b {method} {path} → HTTP {resp.status_code}: {_detail(resp)}")
        return {"success": False, "message": _detail(resp) or f"server_b 返回 HTTP {resp.status_code}"}
    return data if isinstance(data, dict) else {"success": False, "message": "server_b 返回格式异常"}


def _detail(resp) -> str:
    try:
        d = resp.json()
        if isinstance(d, dict):
            detail = d.get("detail") or d.get("message")
            return str(detail)[:300] if detail else ""
    except Exception:
        pass
    return ""


# ─── 业务函数（供路由直接调用）───────────────────────────────────────────
def list_keys(include_disabled: bool = True) -> dict:
    return _call("GET", "/tavily/keys", params={"include_disabled": 1 if include_disabled else 0})


def summary() -> dict:
    return _call("GET", "/tavily/summary")


def add_keys(keys: list, label: str = "") -> dict:
    cleaned = [str(k).strip() for k in (keys or []) if str(k).strip()]
    if not cleaned:
        return {"success": False, "message": "请至少填写一个 key"}
    return _call("POST", "/tavily/keys", body={"keys": cleaned, "label": label})


def delete_key(key_id: int) -> dict:
    return _call("DELETE", f"/tavily/keys/{int(key_id)}")


def set_enabled(key_id: int, enabled: bool, reason: str = "manual") -> dict:
    if enabled:
        return _call("POST", f"/tavily/keys/{int(key_id)}/enable")
    return _call("POST", f"/tavily/keys/{int(key_id)}/disable", body={"reason": reason or "manual"})


def check(ids: list | None = None, force: bool = False) -> dict:
    return _call(
        "POST", "/tavily/check",
        body={"ids": [int(i) for i in (ids or [])], "force": bool(force)},
        timeout=TIMEOUT_CHECK,
    )


# ─── 路由注册（main.py 只加一行调用）────────────────────────────────────
def register_tavily_routes(app) -> None:
    """把 6 个 /api/admin/tavily/* 接口挂到 lobeai app 上。"""

    @app.post("/api/admin/tavily/list")
    async def tavily_list(req: Request, request: TavilyListRequest):
        _require_admin(req)
        return list_keys(request.include_disabled)

    @app.post("/api/admin/tavily/summary")
    async def tavily_summary(req: Request):
        _require_admin(req)
        return summary()

    @app.post("/api/admin/tavily/add")
    async def tavily_add(req: Request, request: TavilyAddRequest):
        operator = _require_admin(req)
        keys = list(request.keys or [])
        if request.key:
            keys.insert(0, request.key)
        logger.info(f"[tavily] {operator} 新增 key：{len(keys)} 个（含重复）")
        return add_keys(keys, request.label)

    @app.post("/api/admin/tavily/delete")
    async def tavily_delete(req: Request, request: TavilyKeyIdRequest):
        operator = _require_admin(req)
        logger.info(f"[tavily] {operator} 删除 key id={request.id}")
        return delete_key(request.id)

    @app.post("/api/admin/tavily/set-enabled")
    async def tavily_set_enabled(req: Request, request: TavilySetEnabledRequest):
        operator = _require_admin(req)
        logger.info(f"[tavily] {operator} {'启用' if request.enabled else '禁用'} key id={request.id}")
        return set_enabled(request.id, request.enabled, request.reason)

    @app.post("/api/admin/tavily/check")
    async def tavily_check(req: Request, request: TavilyCheckRequest):
        operator = _require_admin(req)
        logger.info(f"[tavily] {operator} 触发立即检测 ids={request.ids or '一批'} force={request.force}")
        return check(request.ids, request.force)
