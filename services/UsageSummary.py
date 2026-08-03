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
- claude code 消耗: server_b /billing/consumption（排除表邮箱透传剔除；tokens 表 Σ used_quota）

granularity:
  - ''      只返回累计（summary + by_plan）
  - month   额外返回按自然月分桶（YYYY-MM）
  - week    额外返回按自然周分桶（PG date_trunc('week') 周一为一周起点，YYYY-MM-DD）

排除表：data/excluded_emails.json，{"emails": [...]}，仅限 claude code 套餐统计。
"""
import json
from pathlib import Path

from tools.LoggerManager import LoggerManager
from tools.DbScript import NewApiDatabaseManager
from services.UpdateUserQuotaRequest import _quota_to_rmb, QUOTA_TO_USD
from services.ClaudeCodeActivation import _server_b_url

logger = LoggerManager(log_file="usage_summary.log")

EXCLUDED_FILE = Path(__file__).resolve().parent.parent / "data" / "excluded_emails.json"

# 套餐类型
API = "api"
CLAUDE_CODE = "claude code"

# PG 分桶表达式：month → YYYY-MM；week → 自然周周一 YYYY-MM-DD
_BUCKET_EXPR = {
    "month": "to_char(date_trunc('month', {ts}), 'YYYY-MM')",
    "week": "to_char(date_trunc('week', {ts}), 'YYYY-MM-DD')",
}


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
    分桶：充值/消耗均按 tokens.created_time（int64 秒，token 创建时间）。
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

    bucket_expr = _BUCKET_EXPR.get(granularity)
    recharged_buckets = {}
    consumed_buckets = {}
    if bucket_expr:
        recharged_buckets = _query_buckets(
            db,
            f"SELECT {bucket_expr.format(ts='to_timestamp(created_time)')}, "
            f"COALESCE(SUM(remain_quota + used_quota), 0) FROM tokens "
            f'WHERE "group" = \'api\' AND deleted_at IS NULL GROUP BY 1 ORDER BY 1',
        )
        consumed_buckets = _query_buckets(
            db,
            f"SELECT {bucket_expr.format(ts='to_timestamp(created_time)')}, "
            f'COALESCE(SUM(used_quota), 0) FROM tokens '
            f'WHERE "group" = \'api\' AND deleted_at IS NULL GROUP BY 1 ORDER BY 1',
        )

    return {
        "total_recharged": total_recharged,
        "total_consumed": total_consumed,
        "recharged_buckets": recharged_buckets,
        "consumed_buckets": consumed_buckets,
    }


def _cc_stats(db, excluded: list, granularity: str) -> dict:
    """claude code 套餐：充值 = 已激活码 Σ quota（排除表剔除）

    消耗走 server_b /billing/consumption（排除表透传）。
    分桶：充值按 activation_codes.used_at（timestamptz）。
    """
    ex_cond = ""
    ex_params: tuple = ()
    if excluded:
        placeholders = ",".join(["%s"] * len(excluded))
        ex_cond = f" AND lower(used_by) NOT IN ({placeholders})"
        ex_params = tuple(excluded)

    total_recharged = _query_total(
        db,
        "SELECT COALESCE(SUM(quota), 0) FROM activation_codes "
        "WHERE plan_level = %s AND used_at IS NOT NULL" + ex_cond,
        ("claude code",) + ex_params,
    )

    recharged_buckets = {}
    bucket_expr = _BUCKET_EXPR.get(granularity)
    if bucket_expr:
        recharged_buckets = _query_buckets(
            db,
            f"SELECT {bucket_expr.format(ts='used_at')}, "
            f"COALESCE(SUM(quota), 0) FROM activation_codes "
            f"WHERE plan_level = %s AND used_at IS NOT NULL" + ex_cond +
            " GROUP BY 1 ORDER BY 1",
            ("claude code",) + ex_params,
        )

    # server_b 消耗（排除表透传，server_b 端 tokens 表剔除）
    consumed_buckets = {}
    total_consumed = 0
    try:
        import requests
        url = _server_b_url() + "/billing/consumption"
        params = {"granularity": granularity or "total"}
        if excluded:
            params["exclude"] = ",".join(excluded)
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        total_consumed = int(data.get("total") or 0)
        for b in data.get("buckets") or []:
            consumed_buckets[str(b.get("bucket"))] = int(b.get("quota") or 0)
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

    by_plan = [
        {
            "type": API,
            "total_recharged": round(_quota_to_rmb(api["total_recharged"])),
            "total_consumed": _quota_to_rmb(api["total_consumed"]),
        },
        {
            "type": CLAUDE_CODE,
            "total_recharged": round(_quota_to_rmb(cc["total_recharged"])),
            "total_consumed": _quota_to_rmb(cc["total_consumed"]),
        },
    ]

    result = {
        "currency": "CNY",
        "summary": {
            "total_recharged": round(
                sum(p["total_recharged"] for p in by_plan)
            ),
            "total_consumed": round(sum(p["total_consumed"] for p in by_plan), 2),
        },
        "by_plan": by_plan,
    }

    # 合并各数据源分桶：recharged = api充值 + cc充值；consumed = api消耗 + cc消耗
    # 充值先取整后求和；消耗保留原值（2位小数）
    if granularity in ("month", "week"):
        merged = {}
        for src in (api, cc):
            for bk, quota in src["recharged_buckets"].items():
                merged.setdefault(bk, {"recharged": 0, "consumed": 0})
                merged[bk]["recharged"] += round(_quota_to_rmb(quota))
            for bk, quota in src["consumed_buckets"].items():
                merged.setdefault(bk, {"recharged": 0, "consumed": 0})
                merged[bk]["consumed"] += quota

        key = "by_month" if granularity == "month" else "by_week"
        result[key] = [
            {
                "bucket": bk,
                "recharged": v["recharged"],
                "consumed": _quota_to_rmb(v["consumed"]),
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
