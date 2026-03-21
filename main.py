from fastapi import FastAPI, HTTPException, Depends, Header
from services.NewAPIClient import NewAPIClient
from tools.LoggerManager import LoggerManager
from tools.RequestVaild import *
from services.AdminAuth import AdminAuth
from services.RedemptionService import RedemptionService, GenerateRedemptionRequest

# 初始化 FastAPI 应用
app = FastAPI(title="LobeAI API", version="1.0.0")
loggre = LoggerManager()
new_api_client = NewAPIClient()
redemption_service = RedemptionService()


# 依赖函数，用于验证管理员token
async def get_current_admin(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="授权头格式错误")
    
    token = authorization[7:]  # 移除 "Bearer " 前缀
    username = AdminAuth.verify_token(token)
    
    if username is None:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")
    
    return username


# ==================== API 端点 ====================


@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """
    管理员登录，成功后返回JWT token
    """
    try:
        if AdminAuth.verify_admin_credentials(request.username, request.password):
            token_data = {"sub": request.username}
            token = AdminAuth.create_access_token(token_data)
            return {"access_token": token, "token_type": "bearer"}
        else:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录过程中发生错误: {str(e)}")


@app.get("/api/admin/redemption-codes")
async def get_redemption_codes(
    request: GetRedemptionCodesRequest = Depends(),
    current_admin = Depends(get_current_admin)
):
    """
    查询兑换码列表，需要管理员token
    """
    try:
        redemption_codes = redemption_service.get_filtered_redemption_codes(
            limit=request.limit,
            offset=request.offset,
            is_exchanged=request.is_exchanged,
            plan=request.plan
        )
        total = redemption_service.get_redemption_codes_count()
        
        return {
            "data": redemption_codes,
            "total": total,
            "limit": request.limit,
            "offset": request.offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询兑换码时发生错误: {str(e)}")


@app.post("/api/admin/generate-redemption-codes")
async def generate_redemption_codes(
    request: GenerateRedemptionCodesRequest,
    current_admin = Depends(get_current_admin)
):
    """
    批量生成兑换码，需要管理员token
    前端传入生成数量和套餐类型
    """
    try:
        generated_codes = redemption_service.batch_generate_redemption_codes(
            count=request.count,
            plan=request.plan
        )
        
        return {
            "generated_codes": generated_codes,
            "count": len(generated_codes),
            "plan": request.plan
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成兑换码时发生错误: {str(e)}")


@app.post("/api/admin/delete-redemption-codes")
async def delete_redemption_codes(
    request: DeleteRedemptionCodesRequest,
    current_admin = Depends(get_current_admin)
):
    """
    批量删除兑换码，需要管理员token
    接收要删除的兑换码ID列表
    """
    try:
        deleted_count = redemption_service.batch_delete_redemption_codes(request.ids)
        
        return {
            "deleted_count": deleted_count,
            "ids": request.ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除兑换码时发生错误: {str(e)}")


@app.post("/api/redeem-code")
async def redeem_code(request: RedeemCodeRequest):
    """
    用户兑换兑换码，更新用户email并将兑换标志设为True
    如果兑换码已经被兑换，则返回错误
    """
    try:
        result = redemption_service.redeem_code(request.code, request.email)
        
        return {
            "message": "兑换成功",
            "redeemed_code": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"兑换过程中发生错误: {str(e)}")


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