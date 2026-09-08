"""
InviteStats — 管理员邀请统计 + 套利排查（/api/admin/invite/stats 用，只读）

统计维度（A 端 claude_agent 库）：
1. 被邀请人数：invite_bindings 按 inviter 聚合
2. 累计返利：invite_rewards 聚合（quota + RMB 口径，含充值额）
3. 套利排查：邀请人与被邀请人的登录 IP（user_sessions ip_v4/ip_v6）
   存在交集 → arbitrage_suspected（宽松口径：全量历史 IP 交集≠空）

对疑似套利的邀请人，调 server_b /internal/invite/group-lookup 查其
B 端 token 当前所在分组。背景：backup 分组倍率更高（消耗更快），用于
抑制套利者返利套现，管理员把套利邀请人的 token 挪进 backup 分组视为
"已处理"：
- token 不存在                → token_missing
- token group == 'backup'    → is_backup_group=true（已处理）
- token group != 'backup'    → unprocessed_arbitrage=true（未处理套利用户）

排除表：复用 data/excluded_emails.json（与 usage-summary 同一份），
inviter 或 invitee 命中即该条绑定标 excluded，默认不参与统计与套利判定，
include_excluded=True 可带出。
"""
from tools.LoggerManager import LoggerManager
from tools.DbScript import DatabaseManager
from services.UsageSummary import _load_excluded_emails
from services.ClaudeCodeActivation import _server_b_url, _cf_access_headers

logger = LoggerManager(log_file="invite_stats.log")

BACKUP_GROUP = "backup"


def _get_agent_db():
    """claude_agent 库（invite_bindings / invite_rewards / user_sessions）"""
    import os
    if os.getenv("ENV") == "dev":
        return DatabaseManager(db_name="claude_agent", db_host="127.0.0.1", db_port="2544")
    return DatabaseManager(db_name="claude_agent")


def _lookup_group_via_server_b(email: str) -> dict:
    """调 server_b 查 B 端 token 当前分组，失败返回 {'error': ...}"""
    try:
        import requests
        url = _server_b_url() + "/internal/invite/group-lookup"
        resp = requests.get(
            url,
            params={"email": email},
            timeout=15,
            headers=_cf_access_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[invite-stats] server_b group-lookup 失败 email={email}: {e}")
        return {"error": str(e)}


def _collect_user_ips(db, user_ids: list) -> dict:
    """查 user_sessions，返回 {user_id: set(ip)}（v4/v6 合并，空值剔除）"""
    if not user_ids:
        return {}
    rows = db.execute_query(
        """
        SELECT user_id, ip_v4 FROM user_sessions
         WHERE user_id = ANY(%s) AND ip_v4 IS NOT NULL AND ip_v4 <> ''
        UNION
        SELECT user_id, ip_v6 FROM user_sessions
         WHERE user_id = ANY(%s) AND ip_v6 IS NOT NULL AND ip_v6 <> ''
        """,
        (user_ids, user_ids),
    )
    ip_map: dict = {}
    for uid, ip in rows or []:
        ip_map.setdefault(uid, set()).add(str(ip))
    return ip_map


def get_invite_stats(include_excluded: bool = False) -> dict:
    """邀请统计 + 套利排查主入口（/api/admin/invite/stats 调用）"""
    excluded = _load_excluded_emails()
    excluded_set = set(excluded)

    db = _get_agent_db()
    db.connect()
    if not db.conn:
        return {"status": False, "message": "claude_agent 库连接失败"}

    try:
        # 1. 邀请绑定
        bindings = db.execute_query(
            "SELECT id, inviter_user_id, inviter_email, invitee_user_id, "
            "invitee_email, aff_code, created_at FROM invite_bindings ORDER BY id"
        ) or []

        # 2. 累计返利/充值聚合（按邀请人）
        reward_rows = db.execute_query(
            "SELECT inviter_email, COUNT(*) AS reward_count, "
            "COALESCE(SUM(recharge_quota),0), COALESCE(SUM(recharge_rmb),0), "
            "COALESCE(SUM(reward_quota),0), COALESCE(SUM(reward_rmb),0) "
            "FROM invite_rewards GROUP BY inviter_email"
        ) or []
        reward_map = {
            str(r[0]).strip().lower(): {
                "reward_count": int(r[1] or 0),
                "total_recharge_quota": int(r[2] or 0),
                "total_recharge_rmb": float(r[3] or 0),
                "total_reward_quota": int(r[4] or 0),
                "total_reward_rmb": float(r[5] or 0),
            }
            for r in reward_rows
        }

        # 3. 双方登录 IP 集合（宽松口径：全量历史 IP 交集）
        user_ids = []
        for r in bindings:
            user_ids += [r[1], r[3]]
        ip_map = _collect_user_ips(db, list(set(user_ids)))
    finally:
        db.disconnect()

    # 4. 按邀请人聚合 + IP 交集判定
    inviters: dict = {}
    for bid, inviter_uid, inviter_email, invitee_uid, invitee_email, aff_code, bound_at in bindings:
        inviter_email = str(inviter_email).strip().lower()
        invitee_email = str(invitee_email).strip().lower()
        is_excluded = inviter_email in excluded_set or invitee_email in excluded_set
        if is_excluded and not include_excluded:
            continue

        entry = inviters.setdefault(inviter_email, {
            "inviter_email": inviter_email,
            "invitee_count": 0,
            "invitees": [],
            "total_reward_quota": 0,
            "total_reward_rmb": 0.0,
            "total_recharge_quota": 0,
            "total_recharge_rmb": 0.0,
            "reward_count": 0,
            "arbitrage_suspected": False,
            "matched_ips": [],
            "excluded": False,
        })
        entry["invitee_count"] += 1
        entry["invitees"].append({
            "email": invitee_email,
            "aff_code": aff_code,
            "bound_at": bound_at.isoformat() if bound_at else None,
            "excluded": is_excluded,
        })
        if is_excluded:
            entry["excluded"] = True

        inviter_ips = ip_map.get(inviter_uid, set())
        invitee_ips = ip_map.get(invitee_uid, set())
        matched = sorted(inviter_ips & invitee_ips)
        entry["invitees"][-1]["matched_ips"] = matched
        if matched:
            entry["arbitrage_suspected"] = True
            entry["matched_ips"] = sorted(set(entry["matched_ips"]) | set(matched))

    # 5. 填充返利聚合
    for email, entry in inviters.items():
        agg = reward_map.get(email)
        if agg:
            entry["reward_count"] = agg["reward_count"]
            entry["total_reward_quota"] = agg["total_reward_quota"]
            entry["total_reward_rmb"] = agg["total_reward_rmb"]
            entry["total_recharge_quota"] = agg["total_recharge_quota"]
            entry["total_recharge_rmb"] = agg["total_recharge_rmb"]

    # 6. 疑似套利者查 B 端 token 分组，判定未处理
    for entry in inviters.values():
        entry["token_group"] = None
        entry["is_backup_group"] = None
        entry["unprocessed_arbitrage"] = False
        entry["token_missing"] = False
        if not entry["arbitrage_suspected"] or entry["excluded"]:
            continue

        lookup = _lookup_group_via_server_b(entry["inviter_email"])
        if lookup.get("error"):
            entry["token_group_status"] = "lookup_error"
            continue
        if not lookup.get("token_exists"):
            entry["token_missing"] = True
            continue

        group = (lookup.get("token_group") or "").strip()
        entry["token_group"] = group
        entry["b_remain_quota"] = lookup.get("remain_quota")
        entry["b_used_quota"] = lookup.get("used_quota")
        entry["is_backup_group"] = (group == BACKUP_GROUP)
        if not entry["is_backup_group"]:
            entry["unprocessed_arbitrage"] = True

    result_list = sorted(inviters.values(), key=lambda e: e["inviter_email"])
    summary = {
        "inviter_count": len(result_list),
        "binding_count": sum(e["invitee_count"] for e in result_list),
        "arbitrage_suspected_count": sum(e["arbitrage_suspected"] for e in result_list),
        "unprocessed_arbitrage_count": sum(e["unprocessed_arbitrage"] for e in result_list),
        "total_reward_rmb": round(sum(e["total_reward_rmb"] for e in result_list), 2),
    }
    logger.info(
        f"[invite-stats] ok inviters={summary['inviter_count']} "
        f"arbitrage={summary['arbitrage_suspected_count']} "
        f"unprocessed={summary['unprocessed_arbitrage_count']} excluded={len(excluded)}"
    )
    return {"status": True, "summary": summary, "inviters": result_list}
