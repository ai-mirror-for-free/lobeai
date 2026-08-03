import json
import os
from typing import AsyncIterator

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from services.NewAPIClient import NewAPIClient
from tools.AdminTokenManager import verify_token
from tools.SharedAdminSession import get_admin_client as get_shared_admin_client
from tools.password_encryption import get_decrypted_password

# NewAPI 管理员 role 值
ADMIN_ROLE = 100


def _check_admin_credentials(username, password) -> bool:
    """本地比对管理员账密（NEWAPI_USER + 解密后的密码）

    管理员账号即 lobeai 配置的管理员，本地比对即完成身份校验，
    不向 new-api 发起登录，因此不产生任何 new-api 会话。
    """
    if not username or not password:
        return False
    try:
        expected_user = os.environ.get("NEWAPI_USER", "")
        expected_pass = get_decrypted_password("NEWAPI_PASSWORD_ENCRYPTED")
    except Exception:
        return False
    return username == expected_user and password == expected_pass


def _extract_bearer_token(request: Request) -> str:
    """从 Authorization: Bearer <token> 头提取 token，无则返回空串"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    return ""


async def _extract_body_json(request: Request) -> dict:
    """读取请求体 JSON（幂等，失败返回空 dict）"""
    try:
        raw = await request.body()
        if not raw:
            return {}
        return json.loads(raw) if isinstance(raw, (bytes, str)) else {}
    except Exception:
        return {}


async def get_admin_client(request: Request) -> AsyncIterator[NewAPIClient]:
    """FastAPI 依赖：验证管理员身份并返回共享管理员会话

    凭证优先级（三选一）：
      1. Authorization: Bearer <token> 头
      2. 请求体 token 字段
      3. 请求体 username/password（账密兼容，本地比对）

    认证通过后返回 SharedAdminSession 的全局共享客户端（不登出，
    生命周期与进程一致），保证 new-api 上管理员活跃会话恒为 1。

    注意：本依赖只接收 Starlette Request，手动解析 body，避免与端点自身
    的 body 模型（如 UsageSummaryRequest）在 FastAPI 解析时冲突。
    """
    body = await _extract_body_json(request)
    token = _extract_bearer_token(request) or body.get("token") or ""
    if token:
        entry = await run_in_threadpool(verify_token, token)
        if entry is None:
            raise HTTPException(status_code=401, detail="token invalid or expired")
    elif not _check_admin_credentials(body.get("username"), body.get("password")):
        raise HTTPException(status_code=401, detail="管理员认证失败")

    try:
        client = await run_in_threadpool(get_shared_admin_client)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"管理员会话不可用: {e}")

    yield client
