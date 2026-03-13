"""
OpenWebUI 用户管理脚本
实现用户注册和删除功能

使用方法:
    python user_management.py --base-url http://localhost:8080 --api-key your_api_key
"""

import argparse
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

        response = self.session.post(url, json=payload)

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
            登录成功返回 token 和用户信息
        """
        url = f"{self.base_url}/api/v1/auths/signin"

        payload = {"email": email.lower(), "password": password}

        response = self.session.post(url, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get("detail", response.text)
            raise requests.exceptions.HTTPError(
                f"登录失败 [{response.status_code}]: {error_msg}"
            )


def main():
    parser = argparse.ArgumentParser(description="OpenWebUI 用户管理工具")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8080",
        help="OpenWebUI 服务地址 (默认：http://localhost:8080)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API Key 或 JWT Token (删除用户时需要管理员权限)",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册命令
    register_parser = subparsers.add_parser("register", help="注册新用户")
    register_parser.add_argument("--email", type=str, required=True, help="用户邮箱")
    register_parser.add_argument("--password", type=str, required=True, help="用户密码")
    register_parser.add_argument("--name", type=str, required=True, help="用户名称")
    register_parser.add_argument("--avatar", type=str, help="头像 URL (可选)")

    # 删除命令
    delete_parser = subparsers.add_parser("delete", help="删除用户")
    delete_parser.add_argument("--user-id", type=str, required=True, help="用户 ID")

    # 列表命令
    list_parser = subparsers.add_parser("list", help="列出所有用户")

    # 登录命令
    login_parser = subparsers.add_parser("login", help="用户登录")
    login_parser.add_argument("--email", type=str, required=True, help="用户邮箱")
    login_parser.add_argument("--password", type=str, required=True, help="用户密码")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    client = OpenWebUIClient(base_url=args.base_url, api_key=args.api_key)

    try:
        if args.command == "register":
            print(f"正在注册用户：{args.email}")
            result = client.register_user(
                email=args.email,
                password=args.password,
                name=args.name,
                profile_image_url=args.avatar,
            )
            print("注册成功!")
            print(f"用户 ID: {result.get('id')}")
            print(f"Token: {result.get('token')}")
            print(f"角色：{result.get('role')}")

        elif args.command == "delete":
            print(f"正在删除用户：{args.user_id}")
            result = client.delete_user(args.user_id)
            if result:
                print("用户删除成功!")

        elif args.command == "list":
            print("获取用户列表...")
            users = client.get_users()
            print(f"共找到 {len(users)} 个用户:\n")
            for user in users:
                print(f"  ID: {user.get('id')}")
                print(f"  邮箱：{user.get('email')}")
                print(f"  名称：{user.get('name')}")
                print(f"  角色：{user.get('role')}")
                print("-" * 40)

        elif args.command == "login":
            print(f"正在登录：{args.email}")
            result = client.signin(email=args.email, password=args.password)
            print("登录成功!")
            print(f"用户 ID: {result.get('id')}")
            print(f"Token: {result.get('token')}")
            print(f"角色：{result.get('role')}")

    except requests.exceptions.HTTPError as e:
        print(f"错误：{e}")
    except requests.exceptions.ConnectionError as e:
        print(f"连接错误：无法连接到 {args.base_url}")
        print(f"请确保 OpenWebUI 服务正在运行")
    except Exception as e:
        print(f"发生错误：{e}")


if __name__ == "__main__":
    main()
