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


class RandomActivationCodeRequest(BaseModel):
    """激活码兑换请求"""
    code: str
    username: str
    email: str
    password: str


class GenerateActivationCodesRequest(BaseModel):
    """批量生成激活码请求（仅管理员）"""
    username: str  # 管理员用户名
    password: str  # 管理员密码
    tasks: list[list] = []  # 格式: [[plan_level, days, count], ...]