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


class UpdateUserQuotaRequest(BaseModel):
    """查询并更新用户额度请求"""
    user_id: str
    action: str  # 操作类型：query（查询）或 update（更新）
    quota_type: Optional[str] = None  # 额度类型，如：tokens, requests 等
    amount: Optional[float] = None  # 更新额度时的数量