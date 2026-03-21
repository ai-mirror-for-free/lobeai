from pydantic import BaseModel, Field, validator
from typing import Optional, List
import re


# 1. 发送验证码请求
class SendVerificationCodeRequest(BaseModel):
    email: str = Field(..., description="邮箱地址")

    @validator("email")
    def validate_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("邮箱格式不正确")
        return v


# 2. 用户注册请求
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: str = Field(..., description="邮箱地址")
    verification_code: str = Field(..., min_length=4, max_length=10, description="验证码")
    aff_code: Optional[str] = Field(None, description="推荐码")

    @validator("email")
    def validate_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("邮箱格式不正确")
        return v


# 3. 购买套餐请求
class BuyPackageRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    plan_level: str = Field(..., description="套餐等级")
    days: int = Field(..., ge=1, description="购买天数")


# 4. 更新用户配额请求
class UpdateUserQuotaRequest(BaseModel):
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")


# 5. 管理员登录请求
class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="管理员用户名")
    password: str = Field(..., min_length=1, max_length=100, description="管理员密码")


# 6. 查询兑换码请求
class GetRedemptionCodesRequest(BaseModel):
    limit: int = Field(20, ge=1, le=100, description="每页数量")
    offset: int = Field(0, ge=0, description="偏移量")
    is_exchanged: Optional[bool] = Field(None, description="是否已兑换")
    plan: Optional[str] = Field(None, description="套餐类型")


# 7. 生成兑换码请求
class GenerateRedemptionCodesRequest(BaseModel):
    count: int = Field(..., gt=0, le=1000, description="生成数量，最大1000")
    plan: str = Field(..., min_length=1, max_length=50, description="套餐类型")


# 8. 删除兑换码请求
class DeleteRedemptionCodesRequest(BaseModel):
    ids: List[int] = Field(..., min_items=1, max_items=1000, description="要删除的兑换码ID列表")


# 9. 兑换兑换码请求
class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=255, description="兑换码")
    email: str = Field(..., description="用户邮箱")
    
    @validator("email")
    def validate_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("邮箱格式不正确")
        return v