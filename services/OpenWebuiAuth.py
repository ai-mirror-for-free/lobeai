# Open WebUI 用户认证
import os
import requests
from dotenv import load_dotenv


def get_jwt_token(email, password):
    """
    通过 Open WebUI 的登录接口获取 JWT token。
    :param email: 用户邮箱
    :param password: 用户密码
    :return: JWT token 字符串
    """
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    login_url = f"{base_url.rstrip('/')}/api/v1/auths/signin"
    payload = {
        "email": email,
        "password": password
    }

    try:
        response = requests.post(login_url, json=payload)
        response.raise_for_status()  # 检查 HTTP 错误

        data = response.json()
        token = data.get("token")

        if not token:
            raise Exception("返回数据中未找到 token")

        return token

    except requests.exceptions.HTTPError as e:
        # 获取服务器返回的详细错误信息
        error_msg = e.response.text
        raise Exception(f"请求失败 (状态码 {e.response.status_code}): {error_msg}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"网络请求发生错误：{e}")


def get_jwt_token_with_user_info(email, password):
    """
    通过 Open WebUI 的登录接口获取 JWT token 和用户信息。
    :param email: 用户邮箱
    :param password: 用户密码
    :return: dict 包含 token 和 user_id
    """
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    login_url = f"{base_url.rstrip('/')}/api/v1/auths/signin"
    payload = {
        "email": email,
        "password": password
    }

    try:
        response = requests.post(login_url, json=payload)
        response.raise_for_status()

        data = response.json()
        token = data.get("token")

        # 从返回数据中获取用户 ID (Open WebUI 返回的 id 在根级别)
        user_id = data.get("id")

        if not token:
            raise Exception("返回数据中未找到 token")
        if not user_id:
            raise Exception("返回数据中未找到 user_id")

        return {"token": token, "user_id": user_id}

    except requests.exceptions.HTTPError as e:
        # 获取服务器返回的详细错误信息
        error_msg = e.response.text
        raise Exception(f"请求失败 (状态码 {e.response.status_code}): {error_msg}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"网络请求发生错误: {e}")


def register_user_as_admin(admin_token, name, email, password, role="user"):
    """
    使用管理员权限注册新用户。
    :param admin_token: 管理员 JWT token
    :param name: 用户名
    :param email: 用户邮箱
    :param password: 用户密码
    :param role: 用户角色，默认为 "user"
    :return: 注册结果
    """
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    register_url = f"{base_url.rstrip('/')}/api/v1/auths/add"

    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "name": name,
        "email": email,
        "password": password,
        "role": role
    }

    try:
        response = requests.post(register_url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        return {"success": True, "data": data}

    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text
        return {"success": False, "error": f"请求失败 (状态码 {e.response.status_code}): {error_msg}"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"网络请求发生错误: {e}"}


def get_admin_token():
    """
    获取管理员 token。
    :return: 管理员 JWT token
    """
    load_dotenv()
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")

    if not email or not password:
        raise Exception("请设置 ADMIN_EMAIL 和 ADMIN_PASSWORD 环境变量")

    result = get_jwt_token_with_user_info(email, password)
    return result["token"]
