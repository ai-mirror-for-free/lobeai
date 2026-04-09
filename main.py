import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI, HTTPException
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *

# WAF 规则配置 - 拦截恶意路径
WAF_BLOCK_PATTERNS = [
    r"/api/site/",
    r"/api/index/webconfig",
    r"/api/index/getreaty",
    r"/api/user/ismustmobile",
    r"/apix/",
    r"/api/wanlshop/",
    r"/api/seller/",
    r"/api/BaseInfo/",
    r"/api/Config/",
    r"/api/chat/visitor/",
    r"/api/dict/",
    r"/api/php/",
]

WAF_BLOCK_REGEXES = [re.compile(p, re.IGNORECASE) for p in WAF_BLOCK_PATTERNS]


class WAFMiddleware(BaseHTTPMiddleware):
    """WAF 中间件，拦截恶意请求"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 检查路径是否匹配任何屏蔽规则
        for regex in WAF_BLOCK_REGEXES:
            if regex.search(path):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden", "message": "Access denied by WAF"}
                )

        response = await call_next(request)
        return response


# 初始化 FastAPI 应用
app = FastAPI(title="LobeAI API", version="1.0.0")

# 添加 WAF 中间件
app.add_middleware(WAFMiddleware)

loggre = LoggerManager()
# ==================== API 端点 ====================


@app.post("/api/send-verification-code")
async def send_verification_code(request: SendVerificationCodeRequest):
    """
    1. 发送邮箱验证码
    Args:
        request: 包含邮箱地址的请求体
    """
    email = request.email
    new_api_client = NewAPIClient()
    try:
        new_api_client.send_verification_code(email)
        loggre.info("验证码已发送，请检查邮箱")
        return {"message": "验证码已发送，请检查邮箱"}
    except RuntimeError as e:
        loggre.error(f"发送失败: {e}")
        return {"message": f"发送发送失败: {e}"}


@app.post("/api/register")
async def register_user(request: RegisterRequest):
    """
    2. 用户注册

    Args:
        request: 包含注册信息的请求体

    Returns:
        注册成功消息和用户信息
    """
    from services.CreaterUsers import main_register_user

    username = request.username
    password = request.password
    email = request.email
    verification_code = request.verification_code
    aff_code = request.aff_code
    return main_register_user(
        username=username,
        password=password,
        email=email,
        verification_code=verification_code,
        aff_code=aff_code,
    )


@app.post("/api/random-activation-code")
async def random_activation_code(request: RandomActivationCodeRequest):
    """
    激活码兑换接口
    """
    from services.RandomActivationCode import random_activation_code

    return random_activation_code(
        code=request.code,
        username=request.username,
        email=request.email,
        password=request.password,
    )


@app.post("/api/admin/generate-activation-codes")
async def generate_activation_codes(request: GenerateActivationCodesRequest):
    """
    【管理员】批量生成激活码接口
    tasks: 格式为 [[plan_level, days, count], ...]
    """
    from services.GenerateActivationCodes import batch_generate_activation_codes
    # 每次请求创建独立实例，避免污染全局 session
    admin_client = NewAPIClient()
    try:
        admin_client.session.headers.pop("New-Api-User", None)
        admin_client.session.cookies.clear()
        resp = admin_client.session.post(
            f"{admin_client.base_url}/api/user/login",
            json={"username": request.username, "password": request.password},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise HTTPException(status_code=401, detail=data.get("message", "登录失败"))
        user_data = data.get("data", {})
        user_id = user_data.get("id")
        if user_id:
            admin_client.session.headers.update({"New-Api-User": str(user_id)})
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"管理员认证失败: {e}")

    return batch_generate_activation_codes(
        tasks=request.tasks
    )


@app.post("/api/update-user-quota")
async def update_user_quota(request: UpdateUserQuotaRequest):
    """
    4. 查询并更新用户额度

    Args:
        request: 包含用户ID、操作类型、额度类型和数量的请求体

    Returns:
        查询结果或更新成功消息
    """
    from services.UpdateUserQuotaRequest import get_user_info

    return get_user_info(username=request.username, email=request.email)


# ==================== 健康检查 ====================


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=25141)
