from fastapi import FastAPI, Depends
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *
from tools.VerifyAdmin import get_admin_client

# 初始化 FastAPI 应用
app = FastAPI(title="LobeAI API", version="1.0.0")
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



# ==================== 管理员接口 ====================


@app.post("/api/admin/generate-activation-codes")
async def generate_activation_codes(
    request: GenerateActivationCodesRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】批量生成激活码接口
    tasks: 格式为 [[plan_level, days, count], ...]
    """
    from services.GenerateActivationCodes import batch_generate_activation_codes

    return batch_generate_activation_codes(
        tasks=request.tasks
    )


@app.post("/api/admin/openrouter/models")
async def get_openrouter_models(
    request: AdminAuthRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】获取 OpenRouter 所有模型列表（带缓存）
    """
    from services.OpenRouterPrice import get_all_models, format_model_info

    models = get_all_models()
    return [format_model_info(m) for m in models]


@app.post("/api/admin/openrouter/search")
async def search_openrouter_models(
    request: AdminAuthRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】搜索 OpenRouter 模型

    Args:
        q: 搜索关键词
    """
    from services.OpenRouterPrice import search_models, format_model_info

    models = search_models(request.q)
    return [format_model_info(m) for m in models]


@app.post("/api/admin/price")
async def price_query_page(
    request: AdminAuthRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】OpenRouter 模型价格查询页面（带管理员认证）
    """
    import os
    from fastapi.responses import FileResponse

    template_path = os.path.join(os.path.dirname(__file__), "templates", "price_query.html")
    return FileResponse(template_path)


# ==================== 额度查询 ====================

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
