import os
import datetime
import jwt
import hashlib
from typing import Optional
from dotenv import load_dotenv
from tools.password_encryption import get_decrypted_password

# 加载环境变量
load_dotenv()

SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "your-default-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时过期


class AdminAuth:
    @staticmethod
    def verify_admin_credentials(username: str, password: str) -> bool:
        """
        验证管理员凭据
        """
        admin_username = os.getenv("ADMIN_USERNAME")
        # 从环境变量获取加密的管理员密码并解密
        encrypted_password_env = os.getenv("ADMIN_PASSWORD_ENCRYPTED")

        if not admin_username or not encrypted_password_env:
            raise ValueError("请设置管理员用户名和加密密码环境变量")

        decrypted_password = get_decrypted_password("ADMIN_PASSWORD_ENCRYPTED")

        # 验证用户名和密码
        if username == admin_username and password == decrypted_password:
            return True
        return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
        """
        创建访问令牌
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.datetime.utcnow() + expires_delta
        else:
            expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        # 确保使用PyJWT库的正确方法
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str):
        """
        验证访问令牌
        """
        try:
            # PyJWT库的decode方法
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            return username
        except jwt.exceptions.InvalidTokenError:
            return None
        except Exception:
            return None