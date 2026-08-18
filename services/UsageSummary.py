"""
平台级套餐用量统计（管理员 /api/admin/usage-summary 用，只读）

统计全部套餐的累计充值 + 累计消耗，统一人民币口径。

数据源：
- api 套餐:         server a new api oneapi.tokens WHERE group='api'
                     充值 = Σ(remain_quota+used_quota)，消耗 = Σ used_quota
- claude code 套餐: server_b /billing/consumption（HTTP 直连，同一 SQL 出
                     充值/消耗，排除表邮箱剔除）

口径设计（两个套餐统一）：
- 充值与消耗同源同表（tokens）同时间桶（created_time），单桶「消耗 ≤ 充值」
  数学上恒成立（同批 token 的 used ≤ remain+used），不受 logs 表清理、
  删除 token、以及续费累加不改 created_time 的影响。
- 分桶：month → YYYY-MM；week → 自然周周一 YYYY-MM-DD。

取整：充值/消耗统一 round 2 位小数；单次请求内汇率取一次（rate 参数透传），
避免分桶与汇总因汇率取值时机不同而产生不一致。

granularity:
  - ''      只返回累计（summary + by_plan）
  - month   额外返回按自然月分桶（YYYY-MM）
  - week    额外返回按自然周分桶（YYYY-MM-DD）

排除表：data/excluded_emails.json，{"emails": [...]}，仅限 claude code 套餐统计。
"""
import json
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


def _cc_stats(db, excluded: list, granularity: str) -> dict:
    """claude code 套餐：充值/消耗统一走 server_b tokens 表（同源对称）

    server_b /billing/consumption 一个 SQL 同时出充值(Σ remain+used)与
    消耗(Σ used)，分桶按 token created_time，与 api 套餐同口径，
    单桶消耗恒 ≤ 充值。排除表透传剔除。
    """
    total_recharged = 0
    total_consumed = 0
    recharged_buckets = {}
    consumed_buckets = {}
    try:
        import requests
        url = _server_b_url() + "/billing/consumption"
        params = {"granularity": granularity or "total", "start_ts": 0, "end_ts": 0}
        if excluded:
            params["exclude"] = ",".join(excluded)
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        total_recharged = int(data.get("total_recharged") or 0)
        total_consumed = int(data.get("total_consumed") or 0)
        for b in data.get("buckets") or []:
            bk = str(b.get("bucket"))
            recharged_buckets[bk] = float(b.get("recharged") or 0)
            consumed_buckets[bk] = float(b.get("consumed") or 0)
    except Exception as e:
        logger.error(f"[usage-summary] server_b /billing/consumption 失败: {e}")

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