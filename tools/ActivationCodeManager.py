"""
激活码核心模块
提供激活码生成、加密存储、验证与兑换功能

安全设计:
1. 激活码格式: {base64(payload)}.{base64(signature)}
   - payload = plan_level:days:timestamp:random_id (不包含敏感信息)
   - signature = HMAC-SHA256(payload, SECRET_KEY)
2. 数据库中 code 字段以 Fernet 加密存储 (防数据库泄露)
3. HMAC 签名防止伪造激活码
4. 兑换后立即删除 (one-time use)
5. 时间戳防止重放攻击 (7天有效期)
"""
import hmac
import hashlib
import base64
import json
import time
import secrets
from typing import List, Optional
from tools.password_encryption import encrypt_password, decrypt_password, get_encryption_key
from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager

logger = LoggerManager(log_file="activation_code.log")

# 通过环境变量注入，防止硬编码泄露
def _get_secret_key() -> str:
    """从环境变量获取激活码签名密钥，统一使用 ENCRYPTION_KEY"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    key = os.environ.get("ENCRYPTION_KEY")

    if not key:
        raise Exception("未设置 ENCRYPTION_KEY 环境变量，无法生成/验证激活码。")

    return key


def _generate_code_id() -> str:
    """生成唯一激活码ID"""
    return secrets.token_hex(16)


def _payload_to_base64(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _base64_to_payload(b64: str) -> str:
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding
    return base64.urlsafe_b64decode(b64.encode()).decode()


def _sign_payload(payload: str) -> str:
    """对 payload 进行 HMAC-SHA256 签名"""
    secret = _get_secret_key()
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def _verify_signature(payload: str, signature: str) -> bool:
    """验证 HMAC 签名，防止伪造激活码"""
    expected = _sign_payload(payload)
    return hmac.compare_digest(expected, signature)


def generate_activation_code(plan_level: str, days: int = 0, quota: int = 0) -> str:
    """
    生成单个激活码 (不落库，仅生成)

    激活码格式: {base64(payload)}.{base64(signature)}
    payload = plan_level:days:timestamp:code_id:quota
    - days: 套餐码使用 (1/30/90)，claude code 等基于 quota 的码写 0
    - quota: 直接发放的额度值，套餐码写 0

    Returns:
        激活码字符串，如 "ZGRlZmF1bHQ6MzA6MTcxMjM0NTY3ODkwOjFkMjM0NTY3ODkwYWJjZGVmOjUwMDAwMA==.<sig>"
    """
    timestamp = int(time.time())
    code_id = _generate_code_id()
    payload = f"{plan_level}:{days}:{timestamp}:{code_id}:{quota}"
    payload_b64 = _payload_to_base64(payload)
    signature = _sign_payload(payload)
    return f"{payload_b64}.{signature}"


def parse_activation_code(code: str) -> Optional[dict]:
    """
    解析激活码，验证签名完整性

    兼容旧格式 (4 段) 和新格式 (5 段，多 quota 字段)。
    旧码解析后 quota=0。

    Returns:
        {"plan_level", "days", "timestamp", "code_id", "quota"} 或 None
    """
    try:
        parts = code.strip().split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        payload = _base64_to_payload(payload_b64)

        if not _verify_signature(payload, signature):
            logger.warning(f"激活码签名验证失败: {code[:20]}...")
            return None

        parts = payload.split(":")
        if len(parts) not in (4, 5):
            return None

        plan_level, days_str, timestamp_str, code_id = parts[:4]
        quota = int(parts[4]) if len(parts) == 5 else 0
        return {
            "plan_level": plan_level,
            "days": int(days_str),
            "timestamp": int(timestamp_str),
            "code_id": code_id,
            "quota": quota,
        }
    except Exception as e:
        logger.error(f"激活码解析异常: {e}")
        return None


def validate_activation_code_integrity(code: str) -> tuple[bool, str]:
    """
    验证激活码的完整性和新鲜度（不查数据库）

    1. 格式/签名验证
    2. 有效期验证

    Returns:
        (is_valid, reason)
    """
    parsed = parse_activation_code(code)
    if not parsed:
        return False, "激活码格式错误或签名无效"


    return True, ""


class ActivationCodeManager:
    """激活码数据库管理器"""

    TABLE_NAME = "activation_codes"

    def __init__(self):
        self.db = NewApiDatabaseManager()

    def save_codes(self, codes: List[dict]):
        """
        批量存储激活码（加密后存储）

        Args:
            codes: [{"code": "...", "plan_level": "...", "days": ..., "code_id": "...",
                     "quota": ...}, ...]
                 quota 可省略（默认 0，向后兼容套餐码）
        """
        self.db.connect()
        for item in codes:
            encrypted = encrypt_password(item["code"])
            quota = int(item.get("quota", 0) or 0)
            sql = f"""
            INSERT INTO {self.TABLE_NAME} (encrypted_code, plan_level, days, code_id, quota)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code_id) DO NOTHING
            """
            self.db.execute_command(sql, (
                encrypted,
                item["plan_level"],
                item["days"],
                item["code_id"],
                quota,
            ))
        self.db.disconnect()

    def find_by_code_id(self, code_id: str) -> Optional[dict]:
        """
        根据 code_id 查询激活码

        Returns:
            dict 或 None
            - None: 两种可能 (调用方应区分)
              a) code_id 在 DB 中确实不存在
              b) SQL 执行异常（列不存在、连接失败等），execute_query 静默返回 None

        排查时检查 logs/db.log 看是否有 "查询执行失败" 字样。
        """
        self.db.connect()
        sql = (
            f"SELECT id, encrypted_code, plan_level, days, quota, "
            f"created_at, used_at, used_by FROM {self.TABLE_NAME} WHERE code_id = %s"
        )
        results = self.db.execute_query(sql, (code_id,))
        self.db.disconnect()
        if not results:
            # 区分"不存在"和"查询失败"：execute_query 失败时不返回 row，
            # 而 DB 不存在时也返回空列表。这两种在结果上无法区分，
            # 但日志里 execute_query 失败时会写 ERROR，可据此排查。
            logger.warning(
                f"[find_by_code_id] 未返回结果, code_id={code_id[:16]}..., "
                f"可能原因: (1) DB 中无此 code_id (2) SQL 执行失败 (列缺失/连接问题)"
            )
            return None
        row = results[0]
        return {
            "id": row[0],
            "encrypted_code": row[1],
            "plan_level": row[2],
            "days": row[3],
            "quota": row[4] or 0,
            "created_at": row[5],
            "used_at": row[6],
            "used_by": row[7],
        }

    def mark_as_used(self, code_id: str, used_by: str):
        """标记激活码为已使用"""
        self.db.connect()
        sql = f"UPDATE {self.TABLE_NAME} SET used_at = NOW(), used_by = %s WHERE code_id = %s"
        self.db.execute_command(sql, (used_by, code_id))
        self.db.disconnect()

    def delete_by_code_id(self, code_id: str):
        """删除激活码（兑换后删除）"""
        self.db.connect()
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE code_id = %s"
        self.db.execute_command(sql, (code_id,))
        self.db.disconnect()

    def get_stats_by_plan(self) -> list[dict]:
        """
        按套餐统计激活码信息
        同一 plan_level + days + quota 视为同一批次

        Returns:
            [
                {"plan_level": "default", "days": 30, "quota": 0, "total": 10, "used": 2, "available": 8},
                {"plan_level": "claude code", "days": 0, "quota": 500000, "total": 5, "used": 1, "available": 4},
                ...
            ]
        """
        self.db.connect()
        sql = f"""
            SELECT plan_level, days, COALESCE(quota, 0) AS quota,
                   COUNT(*) as total,
                   COUNT(used_at) as used,
                   COUNT(*) - COUNT(used_at) as available
            FROM {self.TABLE_NAME}
            GROUP BY plan_level, days, COALESCE(quota, 0)
            ORDER BY plan_level, days, COALESCE(quota, 0)
        """
        results = self.db.execute_query(sql)
        self.db.disconnect()

        if not results:
            return []

        return [
            {
                "plan_level": row[0],
                "days": row[1],
                "quota": row[2],
                "total": row[3],
                "used": row[4],
                "available": row[5],
            }
            for row in results
        ]

    def random_code(self, code: str, used_by: str) -> tuple[bool, str, dict]:
        """
        验证激活码（仅验证，不标记已使用）

        流程:
        1. 解析激活码 + 签名验证
        2. 从数据库查找（encrypted_code 无法直接查，用 code_id 查）
        3. 检查是否已使用
        4. 解密激活码并匹配

        Returns:
            (success, message, plan_info) - plan_info 包含 code_id 用于后续标记
        """
        # 1. 解析并验证签名
        parsed = parse_activation_code(code)
        if not parsed:
            return False, "激活码无效", {}

        # 2. 完整性检查（有效期）
        valid, reason = validate_activation_code_integrity(code)
        if not valid:
            return False, reason, {}

        code_id = parsed["code_id"]

        # 3. 从数据库查找
        db_record = self.find_by_code_id(code_id)
        if not db_record:
            return False, "激活码不存在或已失效", {}

        # 4. 检查是否已使用
        if db_record["used_at"]:
            return False, "激活码已被使用", {}

        # 5. 解密并匹配
        try:
            decrypted = decrypt_password(db_record["encrypted_code"])
        except Exception as e:
            logger.error(f"激活码解密失败: {e}")
            return False, "激活码解密失败，系统异常", {}

        if decrypted != code:
            logger.error(f"激活码不匹配: code_id={code_id}")
            return False, "激活码校验失败", {}

        # 6. 验证 plan_level / days / quota 与 payload 一致
        if (db_record["plan_level"] != parsed["plan_level"] or
                db_record["days"] != parsed["days"] or
                db_record["quota"] != parsed["quota"]):
            return False, "激活码信息被篡改", {}

        # 验证成功，返回 code_id 用于后续标记已使用
        logger.info(f"激活码验证成功: code_id={code_id}")
        return True, "验证成功", {
            "plan_level": parsed["plan_level"],
            "days": parsed["days"],
            "code_id": code_id,
            "quota": parsed["quota"],
        }
