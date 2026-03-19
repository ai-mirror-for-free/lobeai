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
    username: str
    email: EmailStr
    password: str
    plan_level: str
    days: int


class UpdateUserQuotaRequest(BaseModel):
    """查询并更新用户额度请求"""
    username: str
    email: EmailStr