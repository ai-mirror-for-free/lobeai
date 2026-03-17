from fastapi import FastAPI, HTTPException
from services.NewAPIClient import NewAPIClient
from tools.logger_manager import LoggerManager
from tools.vaild import *

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
    from services.creater_users import main_register_user
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
    3. 用户购买新套餐

    Args:
        request: 包含用户ID、套餐ID和数量的请求体

    Returns:
        购买成功消息和订单信息
    """
    pass


@app.post("/api/renew-package")
async def renew_package(request: RenewPackageRequest):
    """
    4. 用户续费套餐

    Args:
        request: 包含用户ID、套餐ID和续费月数的请求体

    Returns:
        续费成功消息和新的过期时间
    """
    pass


# ==================== 健康检查 ====================


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=25141)
