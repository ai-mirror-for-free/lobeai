# open_webui 注册用户
import requests
import random
import string
import secrets
import os
from dotenv import load_dotenv
from tools.LoggerManager import LoggerManager
from OpenWebuiAuth import get_admin_token, register_user_as_admin

# Configuration - adjust to your Open WebUI instance URL
load_dotenv()
logger = LoggerManager()


def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_user():
    name = f"user_{generate_random_string()}"
    email = f"{name}@gmail.com"
    password = secrets.token_urlsafe(16)
    return name, email, password


def register_user(name=None, email=None, password=None, role="user"):
    """
    使用管理员权限注册新用户。
    :param name: 用户名
    :param email: 用户邮箱
    :param password: 用户密码
    :param role: 用户角色，默认为 "user"
    :return: 注册是否成功
    """
    logger.info(f"Attempting to register user: {name} ({email})")

    try:
        # 获取管理员 token
        admin_token = get_admin_token()

        # 使用管理员权限注册用户
        result = register_user_as_admin(
            admin_token=admin_token,
            name=name,
            email=email,
            password=password,
            role=role
        )

        if result["success"]:
            logger.info(f"Successfully registered user: {name}")
            logger.info(f"Email: {email}")
            logger.info(f"Password: {password}")
            logger.info(f"Role: {role}")
            return True
        else:
            logger.error(f"Failed to register user: {result['error']}")
            return False

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False
