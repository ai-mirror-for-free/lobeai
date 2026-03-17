from pydantic import BaseModel, EmailStr
from typing import Optional


# ==================== 请求模型 ====================

class SendVerificationCodeRequest(BaseModel):
    """发送邮箱验证码请求"""
    email: EmailStr


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str
    password: str
    email: EmailStr
    verification_code: str
    aff_code: Optional[str] = None


class BuyPackageRequest(BaseModel):
    """用户购买新套餐请求"""
    user_id: str
    package_id: str
    quantity: int = 1


class RenewPackageRequest(BaseModel):
    """用户续费套餐请求"""
    user_id: str
    package_id: str
    duration_months: int