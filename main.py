import requests
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *
from tools.VerifyAdmin import get_admin_client, _check_admin_credentials
from tools.AdminTokenManager import issue_token, TOKEN_TTL
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

    校验用户名+邮箱后，从 NewAPI 数据库中删除用户。
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
    from services.ResendDeliveryChecker import (
        is_known_bounced,
        check_email_delivery,
        mark_bounced,
    )

    email = request.email
    if is_known_bounced(email):
        loggre.warning(f"该邮箱此前已确认退信，拒绝发送: {email}")
        return {"message": "发送失败: 该邮箱不存在或无法接收邮件，请检查邮箱地址"}

    new_api_client = NewAPIClient()
    try:
        new_api_client.send_verification_code(email)
        # 轮询 Resend 投递状态：硬退信（550 邮箱不存在）同步反馈给用户
        delivery = check_email_delivery(email)
        if delivery == "bounced":
            mark_bounced(email)
            loggre.warning(f"验证码投递硬退信（邮箱可能不存在）: {email}")
            return {"message": "发送失败: 该邮箱不存在或无法接收邮件，请检查邮箱地址"}
        loggre.info("验证码已发送，请检查邮箱")
        return {"message": "验证码已发送，请检查邮箱"}
    except (RuntimeError, requests.exceptions.HTTPError) as e:
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

    result = main_register_user(
        username=request.username,
        password=request.password,
        email=request.email,
        verification_code=request.verification_code,
        aff_code=request.aff_code,
    )
    # 业务拒绝（邀请码不符合条件/用户名已存在等）返回 400，
    # 前端对 4xx 有现成的错误展示逻辑，避免 200+success:false 被误当成功
    if isinstance(result, dict) and result.get("success") is False:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/random-activation-code")
async def random_activation_code(request: RandomActivationCodeRequest):
    """
    激活码兑换接口（仅 Claude Code）

    - "claude code"  → 创建/累加 NewAPI token "Claude Code - {email}"
                        (三模型白名单, 永不过期, group="claude code")
                        key 存在则累加 remain_quota，不换 key
    - 其他 plan_level（如历史 default/vip/svip）→ 明确拒绝，且不消耗激活码
    """
    from services.RandomActivationCode import random_activation_code

    return random_activation_code(
        code=request.code,
        username=request.username,
        email=request.email,
        password=request.password,
    )



# ==================== 管理员接口 ====================


@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """
    【管理员】登录换取 lobeai token

    账密本地比对（NEWAPI_USER + 解密密码），不向 new-api 发起登录，
    因此不产生任何 new-api 会话。token 有效期 24 小时。
    """
    import time

    if not _check_admin_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="登录失败")

    token = issue_token(request.username)
    return {
        "success": True,
        "data": {
            "token": token,
            "token_type": "Bearer",
            "expires_at": int(time.time()) + TOKEN_TTL,
            "expires_in": TOKEN_TTL,
        },
    }


@app.post("/api/admin/generate-activation-codes")
async def generate_activation_codes(
    request: GenerateActivationCodesRequest,
    admin_client: NewAPIClient = Depends(get_admin_client)
):
    """
    【管理员】批量生成 Claude Code 激活码接口
    tasks: 格式为 [["claude code", 0, count, price], ...]，price 为人民币
    """
    from services.GenerateActivationCodes import batch_generate_activation_codes

    return batch_generate_activation_codes(
        tasks=request.tasks
    )


@app.post("/api/admin/batch-create-tokens")
async def batch_create_tokens(
    request: BatchCreateTokensRequest,
    admin_client: NewAPIClient = Depends(get_admin_client),
):
    """
    【管理员】批量创建 NewAPI 令牌

    根据套餐类型（data/api.json 中的 key）批量创建令牌，
    输入人民币价格，通过汇率转为美元后计算额度。
    支持自定义过期时间，默认90天。

    Args:
        request: 包含数量、套餐类型、价格、过期时间的请求体
        admin_client: 自动注入的已认证管理员客户端
    """
    from services.BatchCreateTokens import batch_create_tokens as do_batch_create

    return do_batch_create(
        n=request.n,
        package=request.package,
        price=request.price,
        admin_client=admin_client,
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
    返回每种套餐(plan_level + days + 取整价格)的总数、已使用数量、剩余数量。
    汇率波动导致同一取整价格下原始 quota 有微小差异的多批激活码合并为一行,
    额度列显示该组内任意一个原始 quota。
    """
    from collections import defaultdict
    from tools.ActivationCodeManager import ActivationCodeManager
    from services.UpdateUserQuotaRequest import _quota_to_rmb

    manager = ActivationCodeManager()
    stats = manager.get_stats_by_plan()

    # 按取整后的面额重新分组: 同一 (plan_level, days, 取整价格) 视为同一批次
    groups = defaultdict(
        lambda: {"quota": None, "quota_rmb": 0, "total": 0, "used": 0, "available": 0}
    )
    for s in stats:
        rmb = round(_quota_to_rmb(s.get("quota")))
        g = groups[(s["plan_level"], s["days"], rmb)]
        g["quota_rmb"] = rmb
        if g["quota"] is None:
            g["quota"] = s["quota"]
        g["total"] += s["total"]
        g["used"] += s["used"]
        g["available"] += s["available"]

    merged_stats = [
        {
            "plan_level": k[0],
            "days": k[1],
            "quota": g["quota"] or 0,
            "quota_rmb": g["quota_rmb"],
            "total": g["total"],
            "used": g["used"],
            "available": g["available"],
        }
        for k, g in sorted(groups.items())
    ]

    # 计算汇总
    total_all = sum(s["total"] for s in merged_stats)
    used_all = sum(s["used"] for s in merged_stats)
    available_all = sum(s["available"] for s in merged_stats)

    return {
        "stats": merged_stats,
        "summary": {
            "total": total_all,
            "used": used_all,
            "available": available_all,
        }
    }


@app.post("/api/admin/usage-summary")
async def usage_summary(
    request: UsageSummaryRequest,
    admin_client: NewAPIClient = Depends(get_admin_client),
):
    """
    【管理员】平台套餐用量统计
    统计全部套餐(api / claude code)的累计充值 + 累计消耗，人民币口径。
    granularity: ""(只累计) | "month"(按自然月) | "week"(按自然周)
    """
    from services.UsageSummary import get_usage_summary

    return get_usage_summary(granularity=request.granularity)


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



# ==================== 邀请系统 ====================

@app.post("/api/invite/info")
async def invite_info(request: InviteInfoRequest):
    """
    一站式邀请信息：邀请码 + 累计返利 + 邀请人数
    供前端“我的邀请”页一次性拉取
    """
    from services.InviteService import get_user_aff_code, get_invite_rewards_summary
    try:
        code = get_user_aff_code(request.email)
        rewards = get_invite_rewards_summary(request.email)
        return {"success": True, "data": {"email": request.email, "aff_code": code or "", **rewards}}
    except Exception as e:
        return {"success": False, "message": str(e)}

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


# ==================== 额度查询 ====================


@app.post("/api/quota")
async def query_quota(request: QuotaQueryRequest):
    """
    额度查询接口
    输入用户 token (sk-xxx)，返回剩余额度信息
    """
    from services.QuotaQuery import query_quota as do_query
    return do_query(token_key=request.token)


# ==================== 体验接口 ====================


@app.post("/api/experience")
async def experience(request: ExperienceRequest):
    """
    体验接口
    输入用户 key、模型、文本，返回对话结果
    - 文本模型：返回对话内容
    - 图片模型：返回 base64 编码的图片
    """
    from services.ExperienceAPI import call_experience
    return call_experience(key=request.key, model=request.model, text=request.text)


# ==================== 健康检查 ====================


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=25141)
