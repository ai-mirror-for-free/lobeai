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
        self.db = None  # 数据库连接，用于获取完整的 token key

    # ──────────────────────────────────────────────
    # 认证
    # ──────────────────────────────────────────────

    def login(self) -> dict:
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
        username = os.environ.get("NEWAPI_USER")
        password = os.environ.get("NEWAPI_PASSWORD")
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

    def send_verification_code(self, email: str) -> None:
        """
        发送邮箱验证码

        Args:
            email: 邮箱地址

        Raises:
            RuntimeError: 发送失败时抛出
        """
        resp = self.session.get(
            f"{self.base_url}/api/verification",
            params={"email": email},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"发送验证码失败: {data.get('message', '未知错误')}")

    def register(
        self,
        username: str,
        password: str,
        email: str,
        verification_code: str,
        aff_code: str = "",
    ) -> dict:
        """
        用户注册（需要邮箱验证码）

        Args:
            username: 用户名
            password: 密码
            email: 邮箱地址
            verification_code: 邮箱验证码
            aff_code: 推荐码（可选）

        Returns:
            用户信息 dict

        Raises:
            RuntimeError: 注册失败时抛出
        """
        payload = {
            "username": username,
            "password": password,
            "email": email,
            "verification_code": verification_code,
        }
        if aff_code:
            payload["aff_code"] = aff_code

        resp = self.session.post(
            f"{self.base_url}/api/user/register",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"注册失败: {data.get('message', '未知错误')}")

        return data.get("data", {})

    # ──────────────────────────────────────────────
    # 令牌管理
    # ──────────────────────────────────────────────

    def _get_full_token_key_from_db(self, token_id: int) -> dict:
        """
        从数据库获取完整的 token key（绕过 API 的屏蔽）

        Args:
            token_id: 令牌 ID

        Returns:
            包含完整 key 的 token dict，如果查询失败则返回 None
        """
        try:
            from tools.DbScript import NewApiDatabaseManager
            db = NewApiDatabaseManager()
            db.connect()
            # 数据库表结构: id, user_id, key, status, name, created_time, accessed_time, expired_time, ...
            result = db.execute_query(
                "SELECT id, key, name, status, created_time, expired_time, remain_quota, unlimited_quota, model_limits_enabled FROM tokens WHERE id = %s",
                (token_id,)
            )
            db.disconnect()

            if result:
                row = result[0]
                return {
                    "id": row[0],
                    "key": row[1],  # 完整的 key
                    "name": row[2],
                    "status": row[3],
                    "created_time": row[4],
                    "expired_time": row[5],
                    "remain_quota": row[6],
                    "unlimited_quota": row[7],
                    "model_limits_enabled": row[8],
                }
        except Exception as e:
            import sys
            print(f"警告: 无法从数据库获取完整 token key: {e}", file=sys.stderr)
        return None

    def create_token(self, config: TokenConfig) -> dict:
        """
        创建新令牌

        Args:
            config: TokenConfig 实例，描述令牌的配置

        Returns:
            包含 key（sk-xxx）等信息的 dict（key 为完整值）

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

        # 获取最新创建的令牌
        tokens = self.list_tokens(page=0, page_size=1)
        if tokens:
            token = tokens[0]
            token_id = token.get("id")

            # 从数据库获取完整的 key（绕过 API 的屏蔽）
            full_token_data = self._get_full_token_key_from_db(token_id)
            if full_token_data and full_token_data.get("key"):
                # 使用完整 key 更新返回的 token 数据
                token.update(full_token_data)
                return token

            # 如果从数据库获取失败，返回 API 返回的屏蔽 key
            return token

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
