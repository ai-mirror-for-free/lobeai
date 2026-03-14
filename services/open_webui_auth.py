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

        # 从返回数据中获取用户 ID
        user_info = data.get("user", {})
        user_id = user_info.get("id")

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

    

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")

    # 获取 token 和用户信息
    result = get_jwt_token_with_user_info(email, password)
    print(f"Token: {result['token']}")
    print(f"User ID: {result['user_id']}")