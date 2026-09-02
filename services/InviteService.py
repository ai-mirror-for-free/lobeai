"""
InviteService — 复用 new-api users.aff_code 做验真，lobeai 自建 10% 返利

约束（按用户确认）：
- 邀请码直接查 oneapi.users.aff_code 验真（A 侧本地 DB，不走 server_b）
- 邀请者必须已充值：走 server_b /billing/balance 同口径（必须过 server_b HTTP）
- 自邀禁止、一个账号只能被邀请一次、必须新用户（老用户不能补填）
- a 邀 b，b 每次用激活码充值（激活码面额口径 quota → RMB），a 得 10% 无封顶
- 返利归属邀请码所属人（inviter），不允许补填
- 存储：invite_bindings / invite_rewards 落 claude_agent 库（自有业务，不效仿 oneapi 缺陷）
"""

from typing import Optional, Tuple

import requests

from tools.ConfigManager import get_env
from tools.DbScript import DatabaseManager, NewApiDatabaseManager
from tools.LoggerManager import LoggerManager
from tools.GetNewestRate import get_usd_cny_rate
from tools.password_encryption import get_decrypted_password

logger = LoggerManager(log_file="invite.log")

QUOTA_TO_USD = 500000
REWARD_RATE = 0.10



def _get_oneapi_db():
    """oneapi 库：仅用于 aff_code 验真 / users_center / users.inviter_id 查询"""
    return NewApiDatabaseManager()


def _get_agent_db():
    """claude_agent 库：invite_bindings / invite_rewards 自有表"""
    import os
    if os.getenv("ENV") == "dev":
        return DatabaseManager(db_name="claude_agent", db_host="127.0.0.1", db_port="2544")
    return DatabaseManager(db_name="claude_agent")


def _server_b_url() -> str:
    url = (get_env("SERVER_B_URL") or "").strip().rstrip("/")
    if not url:
        raise RuntimeError("未配置 SERVER_B_URL，无法校验邀请者充值状态")
    return url


def _cf_access_headers() -> dict:
    headers = {}
    try:
        import os
        client_id = os.getenv("CF_ACCESS_CLIENT_ID", "")
        secret = get_decrypted_password("CF_ACCESS_CLIENT_SECRET_ENCRYPTED")
        if client_id and secret:
            headers = {
                "CF-Access-Client-Id": client_id,
                "CF-Access-Client-Secret": secret,
            }
    except Exception as e:
        logger.warning(f"[invite] CF access header 未配置，跳过: {e}")
    return headers


def _query_inviter_by_aff_code(aff_code: str) -> Optional[dict]:
    """查 A 侧 oneapi.users，按 aff_code 精确匹配"""
    aff_code = (aff_code or "").strip()
    if not aff_code:
        return None
    db = _get_oneapi_db()
    db.connect()
    if not db.conn:
        logger.error("[invite] A 侧 oneapi 连接失败，无法验邀请码")
        return None
    try:
        with db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, aff_code FROM users WHERE aff_code = %s LIMIT 1",
                (aff_code,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "username": row[1] or "",
                "email": (row[2] or "").strip().lower(),
                "aff_code": row[3] or "",
            }
    except Exception as e:
        logger.error(f"[invite] 查 inviter 失败 aff_code={aff_code}: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            db.disconnect()
        except Exception:
            pass


def _inviter_has_recharged(inviter_email: str) -> Tuple[bool, dict]:
    """走 server_b /billing/balance 同口径判断邀请者是否已充值

    Returns: (has_recharged, raw_balance_dict)
    判定：has_key 且 total_quota>0 视为已充值；unlimited 视为已充值
    """
    inviter_email = (inviter_email or "").strip().lower()
    if not inviter_email:
        return False, {}
    try:
        url = _server_b_url() + "/billing/balance"
        resp = requests.get(
            url,
            params={"email": inviter_email},
            timeout=10,
            headers=_cf_access_headers(),
        )
        resp.raise_for_status()
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(data, dict):
            data = {}
    except Exception as e:
        logger.error(f"[invite] 查询 inviter 余额失败 email={inviter_email}: {e}")
        return False, {}

    has_key = bool(data.get("has_key"))
    total_quota = data.get("total_quota")
    remain = data.get("remain_quota")
    used = data.get("used_quota")
    unlimited = bool(data.get("unlimited"))

    if unlimited:
        return True, data
    if total_quota is not None:
        try:
            if int(total_quota) > 0:
                return True, data
        except Exception:
            pass
    try:
        if int(remain or 0) + int(used or 0) > 0:
            return True, data
    except Exception:
        pass
    if has_key and data.get("remain_quota") is not None:
        try:
            if int(data.get("remain_quota") or 0) > 0:
                return True, data
        except Exception:
            pass
    return False, data


def _quota_to_rmb(quota: int) -> float:
    try:
        rate, _ = get_usd_cny_rate()
        return round(float(quota) / QUOTA_TO_USD * rate, 2)
    except Exception as e:
        logger.error(f"[invite] quota→rmb 失败 quota={quota}: {e}")
        return 0.0


def _rmb_to_quota(rmb: float) -> int:
    try:
        rate, _ = get_usd_cny_rate()
        if rate <= 0:
            return 0
        return int(round(rmb / rate * QUOTA_TO_USD))
    except Exception as e:
        logger.error(f"[invite] rmb→quota 失败 rmb={rmb}: {e}")
        return 0


def calculate_reward(recharge_quota: int) -> Tuple[float, float, int]:
    """按激活码面额算返利

    Returns: (recharge_rmb, reward_rmb, reward_quota)
    """
    recharge_rmb = _quota_to_rmb(int(recharge_quota or 0))
    reward_rmb = round(recharge_rmb * REWARD_RATE, 2)
    if reward_rmb <= 0:
        return recharge_rmb, 0, 0
    reward_quota = _rmb_to_quota(reward_rmb)
    return recharge_rmb, reward_rmb, reward_quota


def validate_invite(aff_code: str, invitee_email: str) -> Tuple[Optional[dict], Optional[str]]:
    """注册前校验邀请码

    Returns: (inviter_dict, error_message)
    """
    invitee_email = (invitee_email or "").strip().lower()
    aff_code = (aff_code or "").strip()
    if not aff_code:
        return None, None
    inviter = _query_inviter_by_aff_code(aff_code)
    if not inviter:
        logger.warning(f"[invite] 邀请码不存在 aff_code={aff_code} invitee={invitee_email}")
        return None, "邀请码不存在"

    inviter_email = (inviter.get("email") or "").strip().lower()

    if invitee_email and inviter_email == invitee_email:
        logger.warning(f"[invite] 自邀禁止 inviter={inviter_email} invitee={invitee_email}")
        return None, "不能邀请自己"

    # 一个账号只能被邀请一次、必须新用户
    # 1) 查 claude_agent invite_bindings（自有表）
    # 2) 查 oneapi users_center / users.inviter_id / users 是否已存在（新用户判定）
    already_bound = False
    is_old_user = False

    # 查 claude_agent 绑定
    adb = _get_agent_db()
    adb.connect()
    try:
        if adb.conn:
            with adb.conn.cursor() as cur:
                cur.execute("SELECT id FROM invite_bindings WHERE invitee_email = %s LIMIT 1", (invitee_email,))
                if cur.fetchone():
                    already_bound = True
    except Exception as e:
        logger.error(f"[invite] 查 claude_agent 绑定失败: {e}")
        try:
            adb.conn.rollback()
        except Exception:
            pass
    finally:
        try:
            adb.disconnect()
        except Exception:
            pass

    # 查 oneapi 侧老用户 / 已有 inviter_id
    odb = _get_oneapi_db()
    odb.connect()
    try:
        if odb.conn:
            with odb.conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users_center WHERE email = %s LIMIT 1", (invitee_email,))
                if cur.fetchone():
                    is_old_user = True
                cur.execute("SELECT inviter_id FROM users WHERE email = %s LIMIT 1", (invitee_email,))
                r = cur.fetchone()
                if r and r[0] and int(r[0]) != 0:
                    already_bound = True
    except Exception as e:
        logger.error(f"[invite] 校验已绑定查询失败: {e}")
        try:
            odb.conn.rollback()
        except Exception:
            pass
    finally:
        try:
            odb.disconnect()
        except Exception:
            pass

    if already_bound:
        return None, "该账号已绑定邀请人，不能重复绑定"
    if is_old_user:
        return None, "仅新用户可使用邀请码，老用户不能补填"

    has_recharged, bal = _inviter_has_recharged(inviter_email)
    if not has_recharged:
        logger.warning(f"[invite] 邀请者未充值 aff_code={aff_code} inviter={inviter_email} bal={bal}")
        return None, "邀请您的邀请者自身没有充值，邀请码无效"

    logger.info(f"[invite] 校验通过 aff_code={aff_code} inviter={inviter_email} invitee={invitee_email} bal={bal}")
    return inviter, None


def create_binding(invitee_email: str, invitee_user_id: int, inviter: dict, aff_code: str) -> Tuple[bool, str]:
    """注册成功后写入 claude_agent.invite_bindings"""
    invitee_email = (invitee_email or "").strip().lower()
    aff_code = (aff_code or "").strip()
    inviter_email = (inviter.get("email") or "").strip().lower()
    inviter_id = int(inviter.get("id") or 0)
    invitee_user_id = int(invitee_user_id or 0)
    if not invitee_email or not invitee_user_id or not inviter_id:
        return False, "参数不完整"

    db = _get_agent_db()
    db.connect()
    if not db.conn:
        logger.error("[invite] 创建绑定失败：claude_agent DB 连接失败")
        return False, "系统繁忙，请稍后重试"
    try:
        with db.conn.cursor() as cur:
            cur.execute("SELECT id FROM invite_bindings WHERE invitee_email = %s OR invitee_user_id = %s LIMIT 1", (invitee_email, invitee_user_id))
            if cur.fetchone():
                logger.warning(f"[invite] 重复绑定 invitee={invitee_email} inviter={inviter_email}")
                return False, "该账号已绑定邀请人"
            cur.execute(
                "INSERT INTO invite_bindings (inviter_user_id, inviter_email, invitee_user_id, invitee_email, aff_code) VALUES (%s,%s,%s,%s,%s)",
                (inviter_id, inviter_email, invitee_user_id, invitee_email, aff_code),
            )
            db.conn.commit()
            logger.info(f"[invite] 绑定成功 invitee={invitee_email}({invitee_user_id}) inviter={inviter_email}({inviter_id}) aff={aff_code}")
            return True, "绑定成功"
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        err = str(e)
        if "unique" in err.lower() or "duplicate" in err.lower():
            logger.warning(f"[invite] 绑定唯一约束冲突 invitee={invitee_email}: {e}")
            return False, "该账号已绑定邀请人"
        logger.error(f"[invite] 创建绑定异常 invitee={invitee_email} inviter={inviter_email}: {e}")
        return False, f"绑定失败: {e}"
    finally:
        try:
            db.disconnect()
        except Exception:
            pass


def get_binding_for_invitee(invitee_email: str) -> Optional[dict]:
    invitee_email = (invitee_email or "").strip().lower()
    if not invitee_email:
        return None
    db = _get_agent_db()
    db.connect()
    if not db.conn:
        return None
    try:
        with db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, inviter_user_id, inviter_email, invitee_user_id, invitee_email, aff_code FROM invite_bindings WHERE invitee_email = %s LIMIT 1",
                (invitee_email,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": int(r[0]),
                "inviter_user_id": int(r[1]),
                "inviter_email": (r[2] or "").strip().lower(),
                "invitee_user_id": int(r[3]),
                "invitee_email": (r[4] or "").strip().lower(),
                "aff_code": r[5] or "",
            }
    except Exception as e:
        logger.error(f"[invite] 查询绑定失败 {invitee_email}: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            db.disconnect()
        except Exception:
            pass


def record_reward(binding_id: int, invitee_email: str, inviter_email: str, activation_code_id: str, recharge_quota: int, recharge_rmb: float, reward_quota: int, reward_rmb: float) -> tuple[bool, bool]:
    """写入 claude_agent.invite_rewards，幂等"""
    db = _get_agent_db()
    db.connect()
    if not db.conn:
        logger.error("[invite] record_reward claude_agent DB 连接失败")
        return False, False
    try:
        with db.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO invite_rewards (binding_id, inviter_email, invitee_email, activation_code_id, recharge_quota, recharge_rmb, reward_quota, reward_rmb) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (activation_code_id, binding_id) DO NOTHING",
                (int(binding_id), inviter_email.strip().lower(), invitee_email.strip().lower(), activation_code_id, int(recharge_quota), float(recharge_rmb), int(reward_quota), float(reward_rmb)),
            )
            is_new = (cur.rowcount or 0) > 0
            db.conn.commit()
            logger.info(f"[invite] 奖励记录写入 binding={binding_id} invitee={invitee_email} code={activation_code_id} recharge={recharge_rmb} reward={reward_rmb} is_new={is_new}")
            return True, is_new
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        logger.error(f"[invite] 写入奖励失败 {invitee_email}->{inviter_email} code={activation_code_id}: {e}")
        return False, False
    finally:
        try:
            db.disconnect()
        except Exception:
            pass



def get_user_aff_code(email: str) -> str:
    """查询用户自己的邀请码（oneapi.users.aff_code），不存在返回空字符串"""
    email = (email or "").strip().lower()
    if not email:
        return ""
    db = _get_oneapi_db()
    db.connect()
    if not db.conn:
        logger.error("[invite] get_user_aff_code DB 连接失败")
        return ""
    try:
        with db.conn.cursor() as cur:
            cur.execute("SELECT aff_code FROM users WHERE email = %s LIMIT 1", (email,))
            r = cur.fetchone()
            if r and r[0]:
                return str(r[0]).strip()
            return ""
    except Exception as e:
        logger.error(f"[invite] 查询 aff_code 失败 {email}: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        return ""
    finally:
        try:
            db.disconnect()
        except Exception:
            pass

def get_invite_rewards_summary(email: str) -> dict:
    """查询用户作为邀请者的累计返利（claude_agent）"""
    email = (email or "").strip().lower()
    if not email:
        return {"invite_count": 0, "total_reward_rmb": 0.0, "total_reward_quota": 0, "rewards": []}
    db = _get_agent_db()
    db.connect()
    if not db.conn:
        logger.error("[invite] get_invite_rewards_summary DB 连接失败")
        return {"invite_count": 0, "total_reward_rmb": 0.0, "total_reward_quota": 0, "rewards": []}
    try:
        with db.conn.cursor() as cur:
            # 邀请人数
            cur.execute("SELECT COUNT(*) FROM invite_bindings WHERE inviter_email = %s", (email,))
            invite_count = int(cur.fetchone()[0] or 0)
            # 累计返利
            cur.execute("SELECT COALESCE(SUM(reward_rmb),0), COALESCE(SUM(reward_quota),0) FROM invite_rewards WHERE inviter_email = %s", (email,))
            row = cur.fetchone()
            total_rmb = float(row[0] or 0)
            total_quota = int(row[1] or 0)
            # 明细
            cur.execute("SELECT invitee_email, activation_code_id, recharge_rmb, reward_rmb, reward_quota, created_at FROM invite_rewards WHERE inviter_email = %s ORDER BY created_at DESC LIMIT 50", (email,))
            rewards = []
            for r in cur.fetchall():
                rewards.append({
                    "invitee_email": r[0],
                    "activation_code_id": r[1],
                    "recharge_rmb": float(r[2]),
                    "reward_rmb": float(r[3]),
                    "reward_quota": int(r[4]),
                    "created_at": str(r[5]),
                })
            return {
                "invite_count": invite_count,
                "total_reward_rmb": round(total_rmb, 2),
                "total_reward_quota": total_quota,
                "rewards": rewards,
            }
    except Exception as e:
        logger.error(f"[invite] 查询返利汇总失败 {email}: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        return {"invite_count": 0, "total_reward_rmb": 0.0, "total_reward_quota": 0, "rewards": []}
    finally:
        try:
            db.disconnect()
        except Exception:
            pass

def reward_inviter_via_server_b(inviter_email: str, reward_quota: int, invitee_email: str, activation_code_id: str) -> Tuple[bool, str]:
    """通过 server_b 给 inviter 加额度（必须过 server_b，不直连 B 库）"""
    inviter_email = (inviter_email or "").strip().lower()
    if not inviter_email or not reward_quota or reward_quota <= 0:
        return False, "参数无效"
    try:
        url = _server_b_url() + "/internal/invite/bonus"
        payload = {
            "inviter_email": inviter_email,
            "quota": int(reward_quota),
            "invitee_email": invitee_email.strip().lower(),
            "activation_code_id": activation_code_id,
        }
        resp = requests.post(url, json=payload, timeout=15, headers=_cf_access_headers())
        resp.raise_for_status()
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(data, dict):
            data = {}
        if data.get("status") or data.get("ok"):
            logger.info(f"[invite] server_b 返利成功 inviter={inviter_email} +{reward_quota} invitee={invitee_email}")
            return True, data.get("message") or "ok"
        logger.warning(f"[invite] server_b 返利返回失败 inviter={inviter_email} resp={data}")
        return False, data.get("message") or str(data)
    except Exception as e:
        logger.error(f"[invite] 调用 server_b 返利异常 inviter={inviter_email}: {e}")
        return False, str(e)
