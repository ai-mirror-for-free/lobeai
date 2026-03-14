"""
New API Client
封装了登录、令牌创建、查询、删除等功能
项目地址: https://github.com/QuantumNous/new-api
"""
import os
import requests
from dataclasses import dataclass, field
from dotenv import load_dotenv

@dataclass
class TokenConfig:
    """创建令牌时的配置项"""
    name: str                          # 令牌名称（必填）
    remain_quota: int = -1             # 可用额度，-1 表示无限制
    expired_time: int = -1             # 过期时间（Unix 时间戳），-1 表示永不过期
    unlimited_quota: bool = True       # 是否无限额度
    model_limits_enabled: bool = False # 是否启用模型限制
    model_limits: str = ""             # 允许的模型，逗号分隔，如 "gpt-4o,claude-3-5-sonnet"
    allow_ips: str = ""                # IP 白名单，逗号分隔，留空表示不限制
    group: str = ""                    # 所属分组，留空使用默认分组


class NewAPIClient:
    """
    New API 管理客户端
    """

    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv("NEWAPI_URL")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.user_id = None

    # ──────────────────────────────────────────────
    # 认证
    # ──────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        """
        登录并保存 Session Cookie

        Args:
            username: 用户名
            password: 密码

        Returns:
            用户信息 dict

        Raises:
            RuntimeError: 登录失败时抛出，包含错误信息
        """
        resp = self.session.post(
            f"{self.base_url}/api/user/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"登录失败: {data.get('message', '未知错误')}")

        user_data = data.get("data", {})
        self.user_id = user_data.get("id")
        if self.user_id:
            self.session.headers.update({"New-Api-User": str(self.user_id)})
        return user_data

    def logout(self) -> None:
        """登出并清除 Session"""
        self.session.get(f"{self.base_url}/api/user/logout")
        self.session.cookies.clear()

    # ──────────────────────────────────────────────
    # 令牌管理
    # ──────────────────────────────────────────────

    def create_token(self, config: TokenConfig) -> dict:
        """
        创建新令牌

        Args:
            config: TokenConfig 实例，描述令牌的配置

        Returns:
            包含 key（sk-xxx）等信息的 dict

        Raises:
            RuntimeError: 创建失败时抛出
        """
        payload = {
            "name": config.name,
            "remain_quota": config.remain_quota,
            "expired_time": config.expired_time,
            "unlimited_quota": config.unlimited_quota,
            "model_limits_enabled": config.model_limits_enabled,
            "model_limits": config.model_limits,
            "allow_ips": config.allow_ips,
            "group": config.group,
        }

        resp = self.session.post(f"{self.base_url}/api/token", json=payload)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"创建令牌失败: {data.get('message', '未知错误')}")

        # API 不直接返回创建的令牌数据，需要查询列表获取
        tokens = self.list_tokens(page=0, page_size=1)
        if tokens:
            return tokens[0]
        raise RuntimeError("创建令牌失败：无法获取新创建的令牌")

    def list_tokens(self, page: int = 0, page_size: int = 10) -> list[dict]:
        """
        查询令牌列表

        Args:
            page:      页码，从 0 开始
            page_size: 每页数量

        Returns:
            令牌列表
        """
        resp = self.session.get(
            f"{self.base_url}/api/token",
            params={"p": page, "page_size": page_size},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"查询令牌失败: {data.get('message', '未知错误')}")

        return data.get("data", {}).get("items", [])

    def get_token(self, token_id: int) -> dict:
        """
        查询单个令牌详情

        Args:
            token_id: 令牌 ID

        Returns:
            令牌详情 dict
        """
        resp = self.session.get(f"{self.base_url}/api/token/{token_id}")
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"查询令牌失败: {data.get('message', '未知错误')}")

        return data.get("data", {})

    def delete_token(self, token_id: int) -> None:
        """
        删除令牌

        Args:
            token_id: 要删除的令牌 ID

        Raises:
            RuntimeError: 删除失败时抛出
        """
        resp = self.session.delete(f"{self.base_url}/api/token/{token_id}")
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"删除令牌失败: {data.get('message', '未知错误')}")

    def update_token_status(self, token_id: int, enabled: bool) -> None:
        """
        启用 / 禁用令牌

        Args:
            token_id: 令牌 ID
            enabled:  True 启用，False 禁用
        """
        status = 1 if enabled else 2
        resp = self.session.put(
            f"{self.base_url}/api/token",
            json={"id": token_id, "status": status},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"更新令牌状态失败: {data.get('message', '未知错误')}")


# ──────────────────────────────────────────────────────
# 使用示例
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    # 1. 初始化客户端
    client = NewAPIClient()
    username = os.environ.get("NEWAPI_USER")
    password = os.environ.get("NEWAPI_PASSWORD")
    # 2. 登录
    user_info = client.login(username, password)
    print(f"登录成功，用户: {user_info.get('username')}")

    # 3. 创建令牌（无限额度，永不过期）
    token = client.create_token(TokenConfig(
        name="my-test-token",
        remain_quota=-1,
        expired_time=-1,
    ))
    print(f"令牌已创建: {token.get('key')}")

    # 4. 创建带限制的令牌（只允许调用 gpt-4o，配额 100000）
    limited_token = client.create_token(TokenConfig(
        name="limited-token",
        remain_quota=100_000,
        unlimited_quota=False,
        model_limits_enabled=True,
        model_limits="gpt-4o,claude-3-5-sonnet-20241022",
    ))
    print(f"限制令牌已创建: {limited_token.get('key')}")

    # 5. 查询令牌列表
    tokens = client.list_tokens(page=0, page_size=20)
    for t in tokens:
        print(f"  [{t['id']}] {t['name']} - {'启用' if t['status'] == 1 else '禁用'}")

    # 6. 禁用令牌
    # client.update_token_status(token["id"], enabled=False)

    # 7. 删除令牌
    # client.delete_token(token["id"])