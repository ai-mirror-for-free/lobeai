from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *
from tools.VerifyAdmin import get_admin_client
from tools.RequestVaild import AdminTextUpdateRequest
from middleware.ProtectionMiddleware import ProtectionMiddleware

# 初始化 FastAPI 应用
app = FastAPI(title="LobeAI API", version="1.0.0")
loggre = LoggerManager()

# ==================== 中间件 ====================

# 防护中间件（拦截扫描器）
app.add_middleware(ProtectionMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ==================== API 端点 ====================


@app.post("/api/reset-password")
async def reset_password(request: ResetPasswordRequest, req: Request):
    """
    忘记密码后重置账号

    校验用户名+邮箱后，从 NewAPI 和 OpenWebUI 数据库中删除用户。
    IP 限流：每小时 3 次失败尝试，超限封禁 1 天。
    """
    from services.ResetPassword import reset_password as do_reset

    return do_reset(request.username, request.email, req)


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
    
    return main_register_user(
        username=request.username,
        password=request.password,
        email=request.email,
        verification_code=request.verification_code,
        aff_code=request.aff_code,
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
    request: AdminOpenRouterSearchRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】搜索 OpenRouter 模型

    Args:
        model_name: 搜索的模型名称
    """
    from services.OpenRouterPrice import search_models, format_model_info

    models = search_models(request.q)
    return [format_model_info(m) for m in models]


@app.post("/api/admin/activation-codes/stats")
async def get_activation_codes_stats(
    request: ActivationCodeStatsRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】查询激活码统计信息
    返回每种套餐(plan_level + days)的总数、已使用数量、剩余数量
    """
    from tools.ActivationCodeManager import ActivationCodeManager

    manager = ActivationCodeManager()
    stats = manager.get_stats_by_plan()

    # 计算汇总
    total_all = sum(s["total"] for s in stats)
    used_all = sum(s["used"] for s in stats)
    available_all = sum(s["available"] for s in stats)

    return {
        "stats": stats,
        "summary": {
            "total": total_all,
            "used": used_all,
            "available": available_all,
        }
    }


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


@app.post("/api/admin/text")
async def update_text(
    request: AdminTextUpdateRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】更新文本并保存到 data 目录
    """
    import json
    import os

    data_dir = os.path.join(os.path.dirname(__file__), "data", "text")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{request.key}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"key": request.key, "content": request.content}, f, ensure_ascii=False, indent=2)

    loggre.info(f"文本已更新: {request.key}")
    return {"message": "文本已更新", "key": request.key}


@app.get("/api/text/{key}")
async def get_text(key: str):
    """
    获取文本内容（无需认证）
    """
    import json
    import os

    file_path = os.path.join(os.path.dirname(__file__), "data", "text", f"{key}.json")
    if not os.path.exists(file_path):
        return {"message": "文本不存在", "key": key}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


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

# ==================== 可用模型展示 ====================
@app.get("/api/available-models")
async def get_available_models():
    """
    获取各套餐的可用模型列表
    """
    import json
    import os

    pricing_path = os.path.join(os.path.dirname(__file__), "data", "pricing_plan.json")
    with open(pricing_path, "r", encoding="utf-8") as f:
        pricing_plan = json.load(f)
    pricing_plan.pop("free", None)
    return pricing_plan

# ==================== 健康检查 ====================


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=25141)
