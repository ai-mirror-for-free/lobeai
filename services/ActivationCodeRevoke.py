"""
激活码反查邮箱 / 额度清零退回（管理员运维，仅管理员界面使用）

对应两个管理员接口的服务层：
1. lookup_activation_code(code)   —— 按激活码反查「谁用了、什么时候用的」（只读）
2. revoke_activation_code(...)    —— 按激活码清零 或 只退回该激活码面额

设计要点
- 激活码 → code_id 直接从 payload 解出（parse_activation_code 已验 HMAC 签名）
- 邮箱来源：A 端 oneapi.activation_codes.used_by（兑换成功时写入）
- 额度操作**必须过 server_b HTTP**（项目硬约束，A 端不直连 B 端库）：
    lobeai → POST server_b /internal/quota/adjust
- 只改 B 端 tokens.remain_quota，不动 used_quota、不禁用 key、不动 status
- mode=refund 有幂等保护：执行前先查 activation_code_revocations 是否已有该
  code_id 的 refund 记录，有则拒绝（防重复扣）。审计表不可用时 fail-closed。
- 审计表 activation_code_revocations 的 DDL 见 lobeai/docs/schema.sql 第 8 节，
  由人工执行；本模块不会自动建表。

换算口径与兑换链路一致：RMB = quota / 500000 * usd_cny_rate
"""
import requests

from tools.DbScript import NewApiDatabaseManager
from tools.LoggerManager import LoggerManager
from tools.password_encryption import decrypt_password

logger = LoggerManager(log_file="activation_code.log")

REVOCATION_TABLE = "activation_code_revocations"

MODE_RESET = "reset"      # 清零该 key 的全部剩余额度
MODE_REFUND = "refund"    # 只退回该激活码的面额
VALID_MODES = (MODE_RESET, MODE_REFUND)

SERVER_B_ADJUST_PATH = "/internal/quota/adjust"


# ─── 内部工具 ────────────────────────────────────────────────────────────


def _query_rows(sql: str, params: tuple) -> list:
    """执行 SELECT 并返回全部行

    Raises:
        RuntimeError: 连接失败 / SQL 执行失败（区别于「0 行」）
    """
    db = NewApiDatabaseManager()
    db.connect()
    if not db.conn:
        raise RuntimeError("DB 连接失败")
    try:
        with db.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"[revoke] SQL 执行失败: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise RuntimeError(f"SQL 执行失败: {e}") from e
    finally:
        db.disconnect()


def _insert_revocation(record: dict) -> tuple[bool, str]:
    """写审计记录，返回 (ok, err_msg)"""
    db = NewApiDatabaseManager()
    db.connect()
    if not db.conn:
        return False, "DB 连接失败"
    sql = f"""
        INSERT INTO {REVOCATION_TABLE}
            (code_id, email, mode, code_quota, before_remain, after_remain,
             deducted, used_quota, token_id, operator, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        record["code_id"],
        record["email"],
        record["mode"],
        int(record.get("code_quota") or 0),
        int(record.get("before_remain") or 0),
        int(record.get("after_remain") or 0),
        int(record.get("deducted") or 0),
        record.get("used_quota"),
        record.get("token_id"),
        record.get("operator") or "",
        record.get("reason") or "",
    )
    try:
        ok = db.execute_command(sql, params)
    finally:
        db.disconnect()
    return (ok, "" if ok else "INSERT 失败，详见日志")


def _find_refund_record(code_id: str) -> dict | None:
    """查该 code_id 是否已执行过退回（幂等保护）

    Raises:
        RuntimeError: 审计表不可用（表不存在 / DB 异常）—— 调用方 fail-closed
    """
    sql = (
        f"SELECT id, before_remain, after_remain, deducted, operator, created_at "
        f"FROM {REVOCATION_TABLE} WHERE code_id = %s AND mode = %s "
        f"ORDER BY id DESC LIMIT 1"
    )
    rows = _query_rows(sql, (code_id, MODE_REFUND))
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row[0],
        "before_remain": row[1],
        "after_remain": row[2],
        "deducted": row[3],
        "operator": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


def _load_code_record(code: str) -> tuple[bool, str, dict, dict]:
    """解析激活码 + 查库 + 解密比对

    Returns:
        (ok, message, parsed, record)
        parsed: parse_activation_code 的返回值（含 code_id / quota）
        record: activation_codes 表行（含 used_at / used_by / plan_level）
    """
    from tools.ActivationCodeManager import ActivationCodeManager, parse_activation_code

    code = (code or "").strip()
    if not code:
        return False, "激活码不能为空", {}, {}

    parsed = parse_activation_code(code)
    if not parsed:
        logger.warning("[revoke] 激活码解析失败（格式/签名无效）")
        return False, "激活码格式错误或签名无效", {}, {}

    code_id = parsed["code_id"]
    manager = ActivationCodeManager()
    try:
        record = manager.find_by_code_id(code_id)
    except RuntimeError as e:
        logger.error(f"[revoke] DB 查询失败: {e}, code_id={code_id}")
        return False, f"系统异常：DB 查询失败 ({e})", {}, {}

    if not record:
        logger.warning(f"[revoke] 激活码不存在: code_id={code_id}")
        return False, "激活码不存在", {}, {}

    # 解密比对：与 random_code 一致的双保险（防「同 code_id 不同密文」）
    try:
        if decrypt_password(record["encrypted_code"]) != code:
            logger.error(f"[revoke] 激活码解密后不匹配: code_id={code_id}")
            return False, "激活码校验失败", {}, {}
    except Exception as e:
        logger.error(f"[revoke] 激活码解密失败: {e}, code_id={code_id}")
        return False, f"激活码解密失败: {e}", {}, {}

    return True, "", parsed, record


def _call_server_b_adjust(
    email: str,
    mode: str,
    quota: int,
    reason: str = "",
    activation_code_id: str = "",
) -> dict:
    """POST server_b /internal/quota/adjust

    Returns:
        成功 → {status: True, before_remain, after_remain, deducted, used_quota, token_id, ...}
        失败 → {status: False, message: "..."}
    """
    from services.ClaudeCodeActivation import _cf_access_headers, _server_b_url

    url = _server_b_url() + SERVER_B_ADJUST_PATH
    payload = {
        "email": email,
        "mode": mode,
        "quota": int(quota),
        "reason": reason or "",
        "activation_code_id": activation_code_id or "",
    }
    try:
        resp = requests.post(
            url, json=payload, timeout=30, headers=_cf_access_headers()
        )
    except requests.exceptions.Timeout:
        logger.error(f"[revoke] server_b 超时: email={email}, mode={mode}")
        return {"status": False, "message": "server_b 额度调整超时"}
    except requests.exceptions.RequestException as e:
        logger.error(f"[revoke] server_b 不可达: {e}, email={email}")
        return {"status": False, "message": f"server_b 不可达: {e}"}

    try:
        data = resp.json()
    except Exception as e:
        logger.error(
            f"[revoke] server_b 返回非 JSON: status={resp.status_code}, err={e}"
        )
        return {"status": False, "message": "server_b 返回格式异常"}

    if resp.status_code >= 400:
        msg = (
            data.get("message")
            or data.get("error")
            or data.get("detail")
            or f"HTTP {resp.status_code}"
        )
        logger.error(f"[revoke] server_b HTTP {resp.status_code}: {msg}")
        return {"status": False, "message": f"额度调整失败: {msg}"}

    if not isinstance(data, dict) or "status" not in data:
        logger.error(f"[revoke] server_b 响应缺 status 字段: {data}")
        return {"status": False, "message": "server_b 响应格式异常"}

    return data


def _rmb(quota, rate=None) -> float:
    """quota → 人民币（复用兑换链路同一换算口径）"""
    from services.UpdateUserQuotaRequest import _quota_to_rmb

    return _quota_to_rmb(quota, rate)


def _current_rate() -> float:
    """取当前 USD→CNY 汇率（A 端库 options.USDExchangeRate 为权威源）

    一次响应内只取一次，避免多次回源；取不到时沿用调用链的兜底值。
    """
    from tools.GetNewestRate import get_usd_cny_rate

    try:
        rate, _ = get_usd_cny_rate()
        return float(rate)
    except Exception as e:
        logger.error(f"[revoke] 汇率获取失败: {e}")
        return 0.0


# ─── 接口 1：按激活码反查邮箱 ────────────────────────────────────────────


def lookup_activation_code(code: str) -> dict:
    """按激活码反查使用邮箱（只读，不触碰 B 端额度）

    Returns:
        {success: True, data: {code_id, plan_level, quota, quota_rmb, days,
                               created_at, used, used_at, used_by, token_name}}
        或 {success: False, message: "..."}
    """
    ok, message, parsed, record = _load_code_record(code)
    if not ok:
        return {"success": False, "message": message}

    used = record["used_at"] is not None
    used_by = (record["used_by"] or "").strip() if used else ""
    quota = int(record["quota"] or 0)

    logger.info(
        f"[lookup] code_id={parsed['code_id']} used={used} used_by={used_by or '-'}"
    )
    return {
        "success": True,
        "data": {
            "code_id": parsed["code_id"],
            "plan_level": record["plan_level"],
            "days": int(record["days"] or 0),
            "quota": quota,
            "quota_rmb": _rmb(quota),
            "created_at": record["created_at"].isoformat() if record["created_at"] else None,
            "used": used,
            "used_at": record["used_at"].isoformat() if record["used_at"] else None,
            "used_by": used_by or None,
            "token_name": f"Claude Code - {used_by}" if used_by else None,
        },
    }


# ─── 接口 2：清零 / 退回额度 ─────────────────────────────────────────────


def revoke_activation_code(
    code: str,
    mode: str,
    operator: str = "",
    reason: str = "",
    dry_run: bool = False,
) -> dict:
    """按激活码清零 / 退回对应 key 的额度

    Args:
        code: 激活码原文
        mode: "reset"（清零全部剩余额度）| "refund"（只退回该码面额）
        operator: 操作人（管理员用户名，审计用）
        reason: 操作原因（审计用）
        dry_run: True 只预览不写库

    Returns:
        {success: True, data: {...before/after/扣除额...}}
        或 {success: False, message: "..."}
    """
    from services.ClaudeCodeActivation import CLAUDE_PLAN_LEVEL

    mode = (mode or "").strip().lower()
    if mode not in VALID_MODES:
        return {"success": False, "message": f"mode 必须为 {'/'.join(VALID_MODES)} 之一"}

    ok, message, parsed, record = _load_code_record(code)
    if not ok:
        return {"success": False, "message": message}

    code_id = parsed["code_id"]

    if record["plan_level"] != CLAUDE_PLAN_LEVEL:
        return {
            "success": False,
            "message": f"该激活码类型为 {record['plan_level']}，非 Claude Code，无法操作额度",
        }
    if record["used_at"] is None:
        return {
            "success": False,
            "message": "该激活码尚未被使用，没有对应邮箱与额度可操作",
        }

    email = (record["used_by"] or "").strip()
    if not email:
        return {"success": False, "message": "激活码使用记录缺少邮箱，无法定位 key"}

    code_quota = int(record["quota"] or 0)
    if int(parsed["quota"]) != code_quota:
        logger.error(
            f"[revoke] 激活码信息不一致: code_id={code_id}, "
            f"payload={parsed['quota']}, db={code_quota}"
        )
        return {"success": False, "message": "激活码信息不一致（payload 与 DB quota 不符）"}

    # refund 幂等保护：同一 code_id 只能退一次；审计表不可用则 fail-closed
    if mode == MODE_REFUND:
        if code_quota <= 0:
            return {"success": False, "message": "该激活码面额为 0，无法退回"}
        try:
            existing = _find_refund_record(code_id)
        except RuntimeError as e:
            logger.error(f"[revoke] 幂等检查失败（审计表不可用）: {e}, code_id={code_id}")
            return {
                "success": False,
                "message": (
                    f"审计表 {REVOCATION_TABLE} 不可用，已拒绝执行以防重复扣额度；"
                    f"请先执行 lobeai/docs/schema.sql 第 8 节 DDL（{e}）"
                ),
            }
        if existing:
            return {
                "success": False,
                "message": (
                    f"该激活码已执行过退回（{existing['created_at']}，操作人 "
                    f"{existing['operator'] or '-'}，已扣 {existing['deducted']}），不可重复退回"
                ),
            }

    logger.info(
        f"[revoke] start code_id={code_id} email={email} mode={mode} "
        f"code_quota={code_quota} operator={operator} dry_run={dry_run} reason={reason!r}"
    )

    # ── dry_run：只读预览（查 server_b 余额，不写任何库）──
    if dry_run:
        from services.UpdateUserQuotaRequest import _server_b_balance

        balance = _server_b_balance(email)
        if not balance or not balance.get("has_key"):
            return {"success": False, "message": f"未找到 {email} 对应的 key（token 不存在）"}
        before_remain = int(balance.get("remain_quota") or 0)
        used_quota = int(balance.get("used_quota") or 0)
        after_remain = (
            0 if mode == MODE_RESET else max(before_remain - code_quota, 0)
        )
        logger.info(
            f"[revoke] dry_run code_id={code_id} email={email} "
            f"{before_remain} → {after_remain}"
        )
        return {
            "success": True,
            "data": _build_result(
                code_id=code_id,
                email=email,
                mode=mode,
                code_quota=code_quota,
                before_remain=before_remain,
                after_remain=after_remain,
                used_quota=used_quota,
                token_id=None,
                operator=operator,
                reason=reason,
                dry_run=True,
                audit_saved=None,
            ),
        }

    # ── 实际执行：调 server_b 改额度 ──
    result = _call_server_b_adjust(
        email=email,
        mode=MODE_RESET if mode == MODE_RESET else "deduct",
        quota=code_quota,
        reason=reason,
        activation_code_id=code_id,
    )
    if not result.get("status"):
        logger.warning(
            f"[revoke] 额度调整失败 code_id={code_id} email={email}: {result.get('message')}"
        )
        return {"success": False, "message": result.get("message") or "额度调整失败"}

    before_remain = int(result.get("before_remain") or 0)
    after_remain = int(result.get("after_remain") or 0)
    used_quota = int(result.get("used_quota") or 0)
    token_id = result.get("token_id")

    # ── 写审计（额度已改，审计失败只告警不回滚）──
    audit_ok, audit_err = _insert_revocation(
        {
            "code_id": code_id,
            "email": email,
            "mode": mode,
            "code_quota": code_quota,
            "before_remain": before_remain,
            "after_remain": after_remain,
            "deducted": result.get("deducted"),
            "used_quota": used_quota,
            "token_id": token_id,
            "operator": operator,
            "reason": reason,
        }
    )
    if not audit_ok:
        logger.error(
            f"[revoke] 审计写入失败（额度已调整，需人工补录）: {audit_err}, "
            f"code_id={code_id} email={email} mode={mode} "
            f"{before_remain} → {after_remain}"
        )

    logger.info(
        f"[revoke] done code_id={code_id} email={email} mode={mode} "
        f"{before_remain} → {after_remain} (deducted={result.get('deducted')}) "
        f"operator={operator} audit_saved={audit_ok}"
    )
    data = _build_result(
        code_id=code_id,
        email=email,
        mode=mode,
        code_quota=code_quota,
        before_remain=before_remain,
        after_remain=after_remain,
        used_quota=used_quota,
        token_id=token_id,
        operator=operator,
        reason=reason,
        dry_run=False,
        audit_saved=audit_ok,
    )
    if not audit_ok:
        data["warning"] = f"额度已调整，但审计记录写入失败（{audit_err}），请人工补录"
    return {"success": True, "data": data}


def _build_result(
    code_id: str,
    email: str,
    mode: str,
    code_quota: int,
    before_remain: int,
    after_remain: int,
    used_quota: int,
    token_id,
    operator: str,
    reason: str,
    dry_run: bool,
    audit_saved,
) -> dict:
    """组装统一响应（quota 与人民币双口径，方便管理员界面直接展示）"""
    rate = _current_rate()

    def rmb(q) -> float:
        return _rmb(q, rate)

    return {
        "code_id": code_id,
        "email": email,
        "token_name": f"Claude Code - {email}",
        "token_id": token_id,
        "mode": mode,
        "code_quota": code_quota,
        "code_quota_rmb": rmb(code_quota),
        "before_remain": before_remain,
        "after_remain": after_remain,
        "deducted": before_remain - after_remain,
        "used_quota": used_quota,
        "before_rmb": rmb(before_remain),
        "after_rmb": rmb(after_remain),
        "deducted_rmb": rmb(before_remain - after_remain),
        "rate": rate,
        "operator": operator,
        "reason": reason,
        "dry_run": dry_run,
        "audit_saved": audit_saved,
    }
