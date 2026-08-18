"""
平台级套餐用量统计（管理员 /api/admin/usage-summary 用，只读）

统计全部套餐的累计充值 + 累计消耗，统一人民币口径。

数据源（全部 server a 可达 / HTTP 直连 server_b）：
- api 套餐充值:     server a new api oneapi.tokens WHERE group='api' 的 Σ(remain_quota+used_quota)
                    （token 生成即算充值；remain+used 恒定=发售价）
- api 套餐消耗:     server a new api oneapi.tokens WHERE group='api' 的 Σ(used_quota)
                    （与充值同源 tokens，口径对称，不受日志清理/删除 token 影响）
- claude code 充值: activation_codes WHERE plan_level='claude code' AND used_at IS NOT NULL
                    （仅已激活码作为充值标准；排除表邮箱剔除）
- claude code 消耗: server_b /billing/consumption/allocated（排除表邮箱剔除；
                    仅返回各 email 累计 used_quota，不做分桶）

分桶口径（claude code 关键修正）：
- recharged 与 consumed 分桶共用 activation_codes.used_at 时间轴 —— consumed 按
  每笔激活码 quota 占该 email 总充值的比例，把该 email 累计消耗分摊到各 used_at 桶。
  数学上每桶「消耗 ≤ 充值」（累计消耗 ≤ 累计充值），彻底避免历史版本按 token
  created_time 落桶导致的「单桶 consumed > recharged」错位。
- api 套餐无累加充值（一次充值一个 token，created_time 即入账时间），分桶保持
  按 created_time，口径天然对称。

取整：充值/消耗统一 round 2 位小数；单次请求内汇率取一次（rate 参数透传），
避免分桶与汇总因汇率取值时机不同而产生不一致。

granularity:
  - ''      只返回累计（summary + by_plan）
  - month   额外返回按自然月分桶（YYYY-MM）
  - week    额外返回按自然周分桶（周一为一周起点，YYYY-MM-DD）

排除表：data/excluded_emails.json，{"emails": [...]}，仅限 claude code 套餐统计。
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager
from tools.GetNewestRate import get_usd_cny_rate
from services.UpdateUserQuotaRequest import _quota_to_rmb
from services.ClaudeCodeActivation import _server_b_url

logger = LoggerManager(log_file="usage_summary.log")

EXCLUDED_FILE = Path(__file__).resolve().parent.parent / "data" / "excluded_emails.json"

# 套餐类型
API = "api"
CLAUDE_CODE = "claude code"


def _load_excluded_emails() -> list:
    """读取排除表（data/excluded_emails.json），返回小写邮箱列表；缺失/损坏 → []"""
    try:
        if EXCLUDED_FILE.exists():
            data = json.loads(EXCLUDED_FILE.read_text(encoding="utf-8"))
            emails = data.get("emails") or []
            return [str(e).strip().lower() for e in emails if str(e).strip()]
    except Exception as e:
        logger.error(f"[usage-summary] 排除表读取失败: {e}")
    return []


def _bucket_key(ts, granularity: str) -> str:
    """unix 秒 → 分桶 key；month → YYYY-MM；week → 自然周周一 YYYY-MM-DD

    claude code 的 recharged/consumed 分桶统一走本函数（同源同口径）。
    """
    d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    if granularity == "month":
        return d.strftime("%Y-%m")
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def _query_total(db, sql: str, params: tuple = ()) -> int:
    """执行单值聚合查询，返回 int（失败 0，不抛）"""
    rows = db.execute_query(sql, params)
    if rows and rows[0] and rows[0][0] is not None:
        return int(rows[0][0])
    return 0


def _query_buckets(db, sql: str, params: tuple = ()) -> dict:
    """执行 bucket 聚合查询，返回 {bucket_key: quota}"""
    rows = db.execute_query(sql, params) or []
    return {str(r[0]): int(r[1]) for r in rows}


def _api_stats(db, granularity: str) -> dict:
    """api 套餐：充值 = Σ(remain_quota+used_quota) tokens；消耗 = Σ used_quota tokens

    充值与消耗同源 tokens 表（口径对称，消耗 ≤ 充值，不受日志清理影响）。
    api 无累加充值（一次充值一个 token），created_time 即入账时间，
    分桶按 tokens.created_time（int64 秒）。
    """
    total_recharged = _query_total(
        db,
        "SELECT COALESCE(SUM(remain_quota + used_quota), 0) FROM tokens "
        'WHERE "group" = \'api\' AND deleted_at IS NULL',
    )
    total_consumed = _query_total(
        db,
        'SELECT COALESCE(SUM(used_quota), 0) FROM tokens '
        'WHERE "group" = \'api\' AND deleted_at IS NULL',
    )

    bucket_expr = None
    if granularity == "month":
        bucket_expr = "to_char(date_trunc('month', to_timestamp(created_time)), 'YYYY-MM')"
    elif granularity == "week":
        bucket_expr = (
            "to_char(date_trunc('week', to_timestamp(created_time)), 'YYYY-MM-DD')"
        )
    recharged_buckets = {}
    consumed_buckets = {}
    if bucket_expr:
        recharged_buckets = _query_buckets(
            db,
            f"SELECT {bucket_expr}, "
            f"COALESCE(SUM(remain_quota + used_quota), 0) FROM tokens "
            f'WHERE "group" = \'api\' AND deleted_at IS NULL GROUP BY 1 ORDER BY 1',
        )
        consumed_buckets = _query_buckets(
            db,
            f"SELECT {bucket_expr}, "
            f'COALESCE(SUM(used_quota), 0) FROM tokens '
            f'WHERE "group" = \'api\' AND deleted_at IS NULL GROUP BY 1 ORDER BY 1',
        )

    return {
        "total_recharged": total_recharged,
        "total_consumed": total_consumed,
        "recharged_buckets": {k: float(v) for k, v in recharged_buckets.items()},
        "consumed_buckets": {k: float(v) for k, v in consumed_buckets.items()},
    }


def _load_cc_recharges(db, excluded: list) -> list:
    """claude code 已核销激活码明细（排除表剔除）

    Returns:
        [{"email": str(小写), "used_at": int(unix 秒), "quota": int}, ...]
    """
    ex_cond = ""
    ex_params: tuple = ()
    if excluded:
        placeholders = ",".join(["%s"] * len(excluded))
        ex_cond = f" AND lower(used_by) NOT IN ({placeholders})"
        ex_params = tuple(excluded)

    sql = (
        "SELECT lower(used_by), "
        "COALESCE(EXTRACT(EPOCH FROM used_at)::bigint, 0), "
        "COALESCE(quota, 0) "
        "FROM activation_codes "
        "WHERE plan_level = %s AND used_at IS NOT NULL" + ex_cond +
        " ORDER BY used_at"
    )
    rows = db.execute_query(sql, ("claude code",) + ex_params) or []
    return [
        {"email": str(r[0]), "used_at": int(r[1]), "quota": int(r[2])}
        for r in rows
    ]


def _cc_stats(db, excluded: list, granularity: str) -> dict:
    """claude code 套餐：充值 = 已激活码 Σ quota；消耗 = 各 email used_quota 按充值比例分摊

    分桶（recharged 与 consumed 同一时间轴）：
    - recharged: 按 activation_codes.used_at
    - consumed:  server_b 返回各 email 累计 used_quota，按该 email 每笔激活码
                  quota 占比分摊到对应 used_at 桶（token 无匹配充值记录时兜底
                  按其 created_time 落桶），保证每桶消耗 ≤ 充值。
    """
    recharges = _load_cc_recharges(db, excluded)
    total_recharged = sum(r["quota"] for r in recharges)

    recharged_buckets = {}
    if granularity in ("month", "week"):
        for r in recharges:
            bk = _bucket_key(r["used_at"], granularity)
            recharged_buckets[bk] = recharged_buckets.get(bk, 0.0) + float(r["quota"])

    # server_b 拿各 email 累计消耗（排除表剔除；不做分桶）
    consumed_buckets = {}
    total_consumed = 0
    try:
        import requests
        url = _server_b_url() + "/billing/consumption/allocated"
        payload = {"granularity": granularity or "total"}
        if excluded:
            payload["exclude"] = ",".join(excluded)
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        total_consumed = int(data.get("total") or 0)

        if granularity in ("month", "week"):
            # 按 email 聚合充值明细，用于比例分摊
            by_email_total: dict = {}
            for r in recharges:
                by_email_total[r["email"]] = (
                    by_email_total.get(r["email"], 0) + r["quota"]
                )
            by_email_used = {item["email"]: item for item in data.get("by_email") or []}

            for email, used in by_email_used.items():
                used = int(used.get("used") or 0)
                created_time = int(used.get("created_time") or 0)
                if not used:
                    continue
                total_q = by_email_total.get(email, 0)
                if total_q > 0:
                    for r in recharges:
                        if r["email"] == email:
                            alloc = used * r["quota"] / float(total_q)
                            bk = _bucket_key(r["used_at"], granularity)
                            consumed_buckets[bk] = consumed_buckets.get(bk, 0.0) + alloc
                elif created_time:
                    # 兜底：token 有消耗但无对应充值记录 → 按创建时间落桶
                    bk = _bucket_key(created_time, granularity)
                    consumed_buckets[bk] = consumed_buckets.get(bk, 0.0) + float(used)
    except Exception as e:
        logger.error(f"[usage-summary] server_b /billing/consumption/allocated 失败: {e}")

    return {
        "total_recharged": total_recharged,
        "total_consumed": total_consumed,
        "recharged_buckets": recharged_buckets,
        "consumed_buckets": consumed_buckets,
    }


def get_usage_summary(granularity: str = "") -> dict:
    """平台套餐用量汇总入口（/api/admin/usage-summary 调用）

    granularity: '' | 'month' | 'week'；'' 只返回累计。
    """
    granularity = (granularity or "").strip().lower()
    if granularity not in ("", "month", "week"):
        granularity = ""

    excluded = _load_excluded_emails()

    # 单次请求统一汇率，保证分桶与汇总口径一致
    rate = None
    try:
        rate, _ = get_usd_cny_rate()
    except Exception as e:
        logger.warning(f"[usage-summary] 汇率读取失败，使用兜底: {e}")

    db = NewApiDatabaseManager()
    db.connect()
    try:
        api = _api_stats(db, granularity)
        cc = _cc_stats(db, excluded, granularity)
    except Exception as e:
        logger.error(f"[usage-summary] 查询失败: {e}")
        raise
    finally:
        db.disconnect()

    # 取整统一：充值/消耗均保留 2 位小数
    by_plan = [
        {
            "type": API,
            "total_recharged": _quota_to_rmb(api["total_recharged"], rate),
            "total_consumed": _quota_to_rmb(api["total_consumed"], rate),
        },
        {
            "type": CLAUDE_CODE,
            "total_recharged": _quota_to_rmb(cc["total_recharged"], rate),
            "total_consumed": _quota_to_rmb(cc["total_consumed"], rate),
        },
    ]

    result = {
        "currency": "CNY",
        "summary": {
            "total_recharged": round(
                sum(p["total_recharged"] for p in by_plan), 2
            ),
            "total_consumed": round(sum(p["total_consumed"] for p in by_plan), 2),
        },
        "by_plan": by_plan,
    }

    # 合并各数据源分桶：recharged = api充值 + cc充值；consumed = api消耗 + cc消耗
    if granularity in ("month", "week"):
        merged = {}
        for src in (api, cc):
            for bk, quota in src["recharged_buckets"].items():
                m = merged.setdefault(bk, {"recharged": 0.0, "consumed": 0.0})
                m["recharged"] += _quota_to_rmb(quota, rate)
            for bk, quota in src["consumed_buckets"].items():
                m = merged.setdefault(bk, {"recharged": 0.0, "consumed": 0.0})
                m["consumed"] += _quota_to_rmb(quota, rate)

        key = "by_month" if granularity == "month" else "by_week"
        result[key] = [
            {
                "bucket": bk,
                "recharged": round(v["recharged"], 2),
                "consumed": round(v["consumed"], 2),
            }
            for bk, v in sorted(merged.items())
        ]

    logger.info(
        f"[usage-summary] ok granularity={granularity or '(total)'} "
        f"excluded={len(excluded)} "
        f"recharged={result['summary']['total_recharged']} "
        f"consumed={result['summary']['total_consumed']}"
    )
    return result