from fastapi import FastAPI, HTTPException
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *

# 初始化 FastAPI 应用
app = FastAPI(title="LobeAI API", version="1.0.0")
loggre = LoggerManager()
new_api_client = NewAPIClient()
# ==================== API 端点 ====================


@app.post("/api/send-verification-code")
async def send_verification_code(request: SendVerificationCodeRequest):
    """
    1. 发送邮箱验证码
    Args:
        request: 包含邮箱地址的请求体
    """
    email = request.email
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


@app.post("/api/buy-package")
async def buy_package(request: BuyPackageRequest):
    """
    3. 用户购买套餐
    username: 用户名
    email: 用户邮箱
    password: 用户密码
    plan_level: 套餐等级
    days: 购买天数
    """
    from services.BuyPackageRequest import buy_package

    username = request.username
    email = request.email
    password = request.password
    plan_level = request.plan_level
    days = request.days
    return buy_package(username, email, password, plan_level, days)


@app.post("/api/random-activation-code")
async def random_activation_code(request: RandomActivationCodeRequest):
    """
    激活码兑换接口
    验证激活码 → 调用 buy_package 充值 → 删除数据库激活码
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
