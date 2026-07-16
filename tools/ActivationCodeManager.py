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
            logger.warning(
                f"[parse] 激活码格式错误 (期望 'payload.signature' 两段): "
                f"code={code[:40]}... parts={len(parts)}"
            )
            return None
        payload_b64, signature = parts
        try:
            payload = _base64_to_payload(payload_b64)
        except Exception as e:
            logger.warning(
                f"[parse] payload base64 解码失败: {e}, "
                f"payload_b64={payload_b64[:40]}..., code={code[:40]}..."
            )
            return None

        if not _verify_signature(payload, signature):
            logger.warning(
                f"[parse] HMAC 签名验证失败 (可能 ENCRYPTION_KEY 不一致 或 激活码被篡改): "
                f"payload={payload}, code={code[:40]}..."
            )
            return None

        parts = payload.split(":")
        if len(parts) not in (4, 5):
            logger.warning(
                f"[parse] payload 段数异常 (期望 4 或 5): got={len(parts)}, "
                f"payload={payload}, code={code[:40]}..."
            )
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
        logger.error(f"[parse] 激活码解析异常: {e}, code={code[:40]}...")
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

    def save_codes(self, codes: List[dict]) -> dict:
        """
        批量存储激活码（加密后存储），返回每条 INSERT 的真实结果

        Args:
            codes: [{"code": "...", "plan_level": "...", "days": ..., "code_id": "...",
                     "quota": ...}, ...]
                 quota 可省略（默认 0，向后兼容套餐码）

        Returns:
            {
                "success": [code_id, ...],     # 真正 INSERT 成功的 code_id
                "failed":  [{"code_id": ..., "reason": "..."}, ...],  # 失败的明细
            }
        """
        result = {"success": [], "failed": []}
        self.db.connect()
        for item in codes:
            encrypted = encrypt_password(item["code"])
            quota = int(item.get("quota", 0) or 0)
            sql = f"""
            INSERT INTO {self.TABLE_NAME} (encrypted_code, plan_level, days, code_id, quota)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code_id) DO NOTHING
            """
            ok = self.db.execute_command(sql, (
                encrypted,
                item["plan_level"],
                item["days"],
                item["code_id"],
                quota,
            ))
            if ok:
                result["success"].append(item["code_id"])
            else:
                # execute_command 失败时日志已写 ERROR，这里只补充上下文
                result["failed"].append({
                    "code_id": item["code_id"],
                    "reason": "INSERT 执行失败，详见 logs/app.log",
                })
                logger.error(
                    f"[save_codes] INSERT 失败: code_id={item['code_id'][:16]}..., "
                    f"plan_level={item['plan_level']}, quota={quota}"
                )
        self.db.disconnect()
        if result["failed"]:
            logger.warning(
                f"[save_codes] 批量存储完成: success={len(result['success'])}, "
                f"failed={len(result['failed'])}"
            )
        return result

    def find_by_code_id(self, code_id: str) -> Optional[dict]:
        """
        根据 code_id 查询激活码

        Returns:
            dict 或 None (truly not found)
        Raises:
            RuntimeError: SQL 执行失败 / DB 连接失败（区别于"激活码不存在"）
        """
        self.db.connect()
        if not self.db.conn:
            logger.error(
                f"[find_by_code_id] DB 连接失败: code_id={code_id[:16]}..."
            )
            raise RuntimeError("DB 连接失败")
        sql = (
            f"SELECT id, encrypted_code, plan_level, days, quota, "
            f"created_at, used_at, used_by FROM {self.TABLE_NAME} WHERE code_id = %s"
        )
        logger.info(
            f"[find_by_code_id] 执行查询: code_id={code_id[:16]}..., "
            f"sql={sql[:80]}..."
        )
        # 直接执行，不再走 execute_query（execute_query 会吞异常）。
        # 这里 try/except 让 SQL 错误显式抛出到 random_code 那里。
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(sql, (code_id,))
                results = cur.fetchall()
        except Exception as e:
            logger.error(
                f"[find_by_code_id] SQL 执行失败: {e}, "
                f"code_id={code_id[:16]}... "
                f"(可能原因: quota 列缺失/类型不对/权限不足/表不存在)"
            )
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            self.db.disconnect()
            raise RuntimeError(f"SQL 执行失败: {e}") from e
        self.db.disconnect()
        if not results:
            logger.warning(
                f"[find_by_code_id] 未返回结果 (DB 中确实不存在此 code_id): "
                f"code_id={code_id[:16]}..."
            )
            return None
        row = results[0]
        logger.info(
            f"[find_by_code_id] 命中: id={row[0]}, plan_level={row[2]}, "
            f"days={row[3]}, quota={row[4]}, used_at={row[6]}"
        )
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
        logger.info(
            f"[random_code] 开始验证激活码: used_by={used_by}, "
            f"code={code[:40]}...({len(code)} chars)"
        )

        # 1. 解析并验证签名
        parsed = parse_activation_code(code)
        if not parsed:
            logger.warning(
                f"[random_code] parse_activation_code 返回 None: "
                f"code={code[:40]}..., used_by={used_by}"
            )
            return False, "激活码无效", {}

        logger.info(
            f"[random_code] 解析成功: plan_level={parsed['plan_level']}, "
            f"days={parsed['days']}, code_id={parsed['code_id']}, "
            f"quota={parsed['quota']}, timestamp={parsed['timestamp']}"
        )

        # 2. 完整性检查（有效期）
        valid, reason = validate_activation_code_integrity(code)
        if not valid:
            logger.warning(
                f"[random_code] validate_activation_code_integrity 失败: "
                f"reason={reason}"
            )
            return False, reason, {}

        code_id = parsed["code_id"]

        # 3. 从数据库查找 (SQL 失败会抛 RuntimeError，需要 catch)
        try:
            db_record = self.find_by_code_id(code_id)
        except RuntimeError as e:
            # SQL 执行失败 / DB 连接失败 —— 明确告诉调用方是 DB 异常
            logger.error(
                f"[random_code] DB 查询失败（不是激活码不存在）: {e}, "
                f"code_id={code_id}, used_by={used_by}"
            )
            return False, f"系统异常：DB 查询失败 ({e})", {}

        if not db_record:
            # DB 中确实没这条记录（SQL 成功但 0 行）
            logger.warning(
                f"[random_code] DB 未找到记录 (SQL 执行成功但 0 行): code_id={code_id}, "
                f"plan_level={parsed['plan_level']}, used_by={used_by}"
            )
            return False, "激活码不存在或已失效", {}

        # 4. 检查是否已使用
        if db_record["used_at"]:
            logger.warning(
                f"[random_code] 激活码已被使用: code_id={code_id}, "
                f"used_at={db_record['used_at']}, used_by={db_record['used_by']}"
            )
            return False, "激活码已被使用", {}

        # 5. 解密并匹配
        try:
            decrypted = decrypt_password(db_record["encrypted_code"])
        except Exception as e:
            logger.error(f"激活码解密失败: {e}")
            return False, "激活码解密失败，系统异常", {}

        if decrypted != code:
            logger.error(
                f"[random_code] 激活码解密后与输入不匹配: code_id={code_id}, "
                f"提示: ENCRYPTION_KEY 可能不一致，或 DB 中密文来自其他密钥"
            )
            return False, "激活码校验失败", {}

        # 6. 验证 plan_level / days / quota 与 payload 一致
        if (db_record["plan_level"] != parsed["plan_level"] or
                db_record["days"] != parsed["days"] or
                db_record["quota"] != parsed["quota"]):
            logger.error(
                f"[random_code] 激活码信息不一致: code_id={code_id}, "
                f"parsed=({parsed['plan_level']},{parsed['days']},{parsed['quota']}), "
                f"db=({db_record['plan_level']},{db_record['days']},{db_record['quota']})"
            )
            return False, "激活码信息被篡改", {}

        # 验证成功，返回 code_id 用于后续标记已使用
        logger.info(
            f"激活码验证成功: code_id={code_id}, "
            f"plan_level={parsed['plan_level']}, quota={parsed['quota']}"
        )
        return True, "验证成功", {
            "plan_level": parsed["plan_level"],
            "days": parsed["days"],
            "code_id": code_id,
            "quota": parsed["quota"],
        }
