"""
OpenWebUI 用户管理脚本
实现用户注册和删除功能

使用方法:
    python user_management.py --base-url http://localhost:8080 --api-key your_api_key
"""

import requests
from typing import Optional


class OpenWebUIClient:
    """OpenWebUI API 客户端"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        初始化客户端

        Args:
            base_url: OpenWebUI 服务地址，如 http://localhost:8080
            api_key: API Key 或 JWT Token (用于删除用户等需要认证的操作)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def register_user(
        self,
        email: str,
        password: str,
        name: str,
        profile_image_url: Optional[str] = None,
    ) -> dict:
        """
        注册新用户

        Args:
            email: 用户邮箱
            password: 用户密码
            name: 用户名称
            profile_image_url: 可选的头像 URL

        Returns:
            注册成功返回用户信息和 token

        Raises:
            requests.exceptions.HTTPError: 注册失败时抛出
        """
        url = f"{self.base_url}/api/v1/auths/signup"

        payload = {
            "email": email.lower(),
            "password": password,
            "name": name,
        }

        if profile_image_url:
            payload["profile_image_url"] = profile_image_url

        # 创建一个不含 Authorization 的 header 副本
        headers = {k: v for k, v in self.session.headers.items() if k != "Authorization"}

        # 使用该 headers 发送 POST 请求
        response = self.session.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"注册失败 [{response.status_code}]: {error_msg}"
            )

    def delete_user(self, user_id: str) -> bool:
        """
        删除指定用户

        Args:
            user_id: 要删除的用户 ID

        Returns:
            删除成功返回 True

        Raises:
            requests.exceptions.HTTPError: 删除失败时抛出
        """
        url = f"{self.base_url}/api/v1/users/{user_id}"

        response = self.session.delete(url)

        if response.status_code == 200:
            return True
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"删除失败 [{response.status_code}]: {error_msg}"
            )

    def get_users(self) -> list:
        """
        获取所有用户列表

        Returns:
            用户列表
        """
        url = f"{self.base_url}/api/v1/users/"

        response = self.session.get(url)

        if response.status_code == 200:
            data = response.json()
            return data.get("users", [])
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"获取用户列表失败 [{response.status_code}]: {error_msg}"
            )

    def get_user_by_id(self, user_id: str) -> dict:
        """
        根据 ID 获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户信息字典
        """
        url = f"{self.base_url}/api/v1/users/{user_id}"

        response = self.session.get(url)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"获取用户信息失败 [{response.status_code}]: {error_msg}"
            )

    def signin(self, email: str, password: str) -> dict:
        """
        用户登录

        Args:
            email: 用户邮箱
            password: 用户密码

        Returns:
            登录成功返回信息 (包含 token)
        """
        url = f"{self.base_url}/api/v1/auths/signin"
        payload = {
            "email": email.lower(),
            "password": password,
        }

        response = self.session.post(url, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"登录失败 [{response.status_code}]: {error_msg}"
            )

    def login_and_set_token(self, email: str, password: str) -> str:
        """
        登录并自动设置 Session 的 Authorization 头

        Returns:
            获取到的 token
        """
        result = self.signin(email, password)
        token = result.get("token")
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.api_key = token
            return token
        else:
            raise Exception("登录返回结果中未找到 token")


def main():
    """
    示例用法演示
    
    展示如何使用 OpenWebUIClient 进行用户管理操作
    """
    # 配置参数
    BASE_URL = "http://localhost:8080"
    API_KEY = "your_api_key_here"  # 替换为您的 API Key
    
    # 创建客户端实例，初始不带 API Key
    client = OpenWebUIClient(base_url=BASE_URL)

    print("=" * 60)
    print("OpenWebUI 用户管理示例")
    print("=" * 60)

    try:
        # 示例 1: 用户注册
        print("\n[示例 1] 用户注册")
        print("-" * 40)
        new_user_email = "newuser@example.com"
        new_user_password = "secure_password123"
        new_user_name = "新用户"

        print(f"注册用户：{new_user_email}")
        register_result = client.register_user(
            email=new_user_email,
            password=new_user_password,
            name=new_user_name,
        )
        print(f"✓ 注册成功!")
        print(f"  用户 ID: {register_result.get('id')}")

        # 登录并获取 token
        print(f"\n[示例 2] 用户登录")
        print("-" * 40)
        client.login_and_set_token(new_user_email, new_user_password)
        print(f"✓ 登录成功并已设置 Token!")

        # 示例 3: 获取用户列表
        print("\n[示例 3] 获取用户列表")
        print("-" * 40)
        users = client.get_users()
        print(f"共找到 {len(users)} 个用户:")
        for idx, user in enumerate(users, 1):
            print(f"\n  [{idx}] ID: {user.get('id')}")
            print(f"      邮箱：{user.get('email')}")
            print(f"      名称：{user.get('name')}")
            print(f"      角色：{user.get('role')}")

        # 示例 4: 根据 ID 获取用户信息
        if users:
            print("\n[示例 4] 获取指定用户信息")
            print("-" * 40)
            user_id = users[0].get('id')
            print(f"查询用户 ID: {user_id}")
            user_info = client.get_user_by_id(user_id)
            print(f"✓ 获取成功!")
            print(f"  邮箱：{user_info.get('email')}")
            print(f"  名称：{user_info.get('name')}")
            print(f"  角色：{user_info.get('role')}")

        print("\n" + "=" * 60)
        print("所有示例执行完成!")
        print("=" * 60)

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP 错误：{e}")
        print("\n提示：请确保")
        print("  1. OpenWebUI 服务正在运行")
        print("  2. 请求参数符合要求")
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接错误：无法连接到 {BASE_URL}")
        print("请确保 OpenWebUI 服务正在运行")
    except Exception as e:
        print(f"\n❌ 发生错误：{e}")


if __name__ == "__main__":
    main()
