import time
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ==================== 防护配置 ====================

NOTFOUND_LIMIT = 3          # 短时间内 404 次数阈值
NOTFOUND_WINDOW = 60         # 时间窗口(秒)
NOTFOUND_BLOCK_SECONDS = 300 # 触发后封禁时长(秒)

# 排除不记入 404 计数的正常路径(白名单)
EXCLUDE_PATHS = [
    "/health",
    "/api/available-models",
]

# 内存存储
ip_notfound: dict[str, list[float]] = defaultdict(list)
ip_blocked: dict[str, float] = {}


def _get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class ProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _get_client_ip(request)
        path = request.url.path

        # 1. 检查是否被封禁
        if ip in ip_blocked:
            if time.time() - ip_blocked[ip] < NOTFOUND_BLOCK_SECONDS:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests, please try later."},
                )
            else:
                del ip_blocked[ip]

        # 2. 清理过期记录
        now = time.time()
        ip_notfound[ip] = [t for t in ip_notfound[ip] if now - t < NOTFOUND_WINDOW]

        # 3. 发起请求
        response = await call_next(request)

        # 4. 记录 404
        if response.status_code == 404 and path not in EXCLUDE_PATHS:
            ip_notfound[ip].append(now)

            # 5. 检查是否超限
            if len(ip_notfound[ip]) >= NOTFOUND_LIMIT:
                ip_blocked[ip] = now
                ip_notfound[ip].clear()
                print(f"[BLOCKED] ip={ip} 404_count={NOTFOUND_LIMIT} in {NOTFOUND_WINDOW}s")
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests, please try later."},
                )

        return response
