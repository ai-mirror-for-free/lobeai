"""
密码加密/解密工具模块
使用 Fernet 对称加密保护敏感信息

密钥通过环境变量 ENCRYPTION_KEY 注入，适用于本地开发和服务器部署
"""
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken


def generate_encryption_key() -> str:
    """
    生成新的加密密钥
    :return: 加密密钥字符串
    """
    key = Fernet.generate_key()
    return key.decode()


def get_encryption_key() -> str:
    """
    获取加密密钥

    从环境变量 ENCRYPTION_KEY 读取密钥

    Returns:
        加密密钥

    Raises:
        Exception: 无法获取密钥
    """
    load_dotenv()
    key = os.environ.get("ENCRYPTION_KEY")

    if not key:
        raise Exception(
            "无法获取加密密钥。请设置 ENCRYPTION_KEY 环境变量\n"
            "示例：\n"
            "  export ENCRYPTION_KEY=\"your_key_here\"\n"
            "  python your_script.py"
        )

    return key


def encrypt_password(password: str, key: str = None) -> str:
    """
    加密密码
    :param password: 明文密码
    :param key: 加密密钥（可选，默认从环境变量读取）
    :return: 加密后的密码
    """
    if key is None:
        key = get_encryption_key()

    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str, key: str = None) -> str:
    """
    解密密码
    :param encrypted_password: 加密的密码
    :param key: 加密密钥（可选，默认从环境变量读取）
    :return: 明文密码
    """
    if key is None:
        key = get_encryption_key()

    fernet = Fernet(key.encode())
    try:
        decrypted = fernet.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except InvalidToken:
        raise Exception("解密失败：密钥不正确或密码已损坏")


# 便捷函数：从环境变量解密密码
def get_decrypted_password(env_var_name: str) -> str:
    """
    从环境变量读取并解密密码
    :param env_var_name: 环境变量名
    :return: 解密后的明文密码
    """
    load_dotenv()
    encrypted_password = os.environ.get(env_var_name)

    if not encrypted_password:
        raise Exception(f"环境变量 {env_var_name} 未设置")

    return decrypt_password(encrypted_password)
