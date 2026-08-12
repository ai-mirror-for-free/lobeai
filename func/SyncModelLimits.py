"""
同步 NewAPI 令牌 (group="api") 的模型限制

本脚本启动时先调用 func/SyncApiJson.sync_api_json() 从 new-api 的
OpenRouter / Vertex AI 渠道拉取最新模型并更新 data/api.json，
再执行令牌 model_limits 同步：
1. 通过 load_api_config 加载最新的 api.json 模型列表
2. 查询 NewAPI 数据库中 group="api" 的令牌（命名规则 batch-{package}-{ts}-{i}）
3. 检查并按 api.json[package] 更新 token 的 model_limits

注意：
- 套餐体系（default/vip/svip）已下线，OpenWebUI 同步逻辑已移除。
- Claude Code 令牌 (group="claude code") 继续排除。
- 旧版 default/vip/svip group 的存量令牌视为历史遗留，名字无法解析为 package 时跳过。
- 模型白名单与 api.json 严格一致（不再有 extra_modellist 追加项）。
"""

import json
import re
from tools.DbScript import NewApiDatabaseManager
from tools.LoggerManager import LoggerManager
from tools.LoadApiConfig import load_api_config
from func.SyncApiJson import sync_api_json

logger = LoggerManager(log_file="sync_model_limits.log")
newapidata = NewApiDatabaseManager()

# 名称规则来自 services/BatchCreateTokens.batch_create_tokens
BATCH_TOKEN_PATTERN = re.compile(r"^batch-(?P<package>[^-]+)-\d+-\d+$")

# 排除 group
EXCLUDED_GROUP = ["claude code"]


def _get_all_tokens_from_db():
    """从 NewAPI 数据库获取所有令牌（含完整 key）"""
    newapidata.connect()
    result = newapidata.execute_query("""
        SELECT id, key, name, status, remain_quota, unlimited_quota,
               model_limits_enabled, model_limits, "group"
        FROM tokens
        ORDER BY id
    """)
    newapidata.disconnect()
    return result


def _parse_package_from_token_name(token_name: str) -> str | None:
    """
    从令牌名解析 package；不能解析返回 None。
    命名规则: batch-{package}-{timestamp}-{index}
    """
    m = BATCH_TOKEN_PATTERN.match(token_name or "")
    if not m:
        return None
    return m.group("package")


def _parse_model_limits(model_limits_str: str) -> list:
    """解析逗号分隔的模型列表"""
    if not model_limits_str:
        return []
    return [m.strip() for m in model_limits_str.split(",") if m.strip()]


def _list_equals(list1: list, list2: list) -> bool:
    """比较两个列表是否相同（忽略顺序）"""
    return sorted(list1) == sorted(list2)


def _update_token_model_limits(token_id: int, model_limits: str) -> bool:
    """更新令牌 model_limits"""
    newapidata.connect()
    result = newapidata.execute_command(
        "UPDATE tokens SET model_limits = %s WHERE id = %s",
        (model_limits, token_id)
    )
    newapidata.disconnect()
    return result


def sync_model_limits():
    """
    主同步流程
    """
    # Step 0: 先从 new-api 渠道同步最新模型到 api.json
    sync_api_json()

    # Step 1: 加载 api.json
    api_config = load_api_config()
    logger.info(f"加载 api.json 套餐: {list(api_config.keys())}")

    # Step 2: 查询所有令牌
    tokens = _get_all_tokens_from_db()
    logger.info(f"从数据库获取到 {len(tokens)} 个令牌")

    updated_count = 0
    skipped_count = 0

    for token_row in tokens:
        token_id, token_key, token_name, status, remain_quota, \
            unlimited_quota, model_limits_enabled, model_limits, token_group = token_row

        # Step 3: 仅处理 group="api" 的令牌
        if token_group != "api":
            logger.info(f"跳过非 api 分组令牌 ({token_group}): {token_name}")
            skipped_count += 1
            continue

        # Step 4: 从名称解析 package
        package = _parse_package_from_token_name(token_name)
        if package is None:
            logger.warning(f"无法从名称解析 package，跳过: {token_name}")
            skipped_count += 1
            continue
        if package not in api_config:
            logger.warning(
                f"令牌 {token_name} 的 package={package} 不在 api.json 中，跳过"
            )
            skipped_count += 1
            continue

        # Step 5: 计算期望模型列表 (api.json[package])
        expected_models = list(api_config[package])
        current_models = _parse_model_limits(model_limits)

        if _list_equals(current_models, expected_models):
            logger.info(f"令牌 {token_name} (package={package}) 模型列表无需更新")
            skipped_count += 1
            continue

        logger.info(
            f"令牌 {token_name} (package={package}) 模型列表不一致，需要更新:"
        )
        logger.info(f"  当前: {current_models}")
        logger.info(f"  期望: {expected_models}")

        new_model_limits = ",".join(expected_models)
        if _update_token_model_limits(token_id, new_model_limits):
            logger.info(f"  -> NewAPI token model_limits 已更新")
            updated_count += 1
        else:
            logger.error(f"  -> NewAPI token model_limits 更新失败")
            skipped_count += 1

    logger.info(f"同步完成: 更新 {updated_count} 个令牌, 跳过 {skipped_count} 个")
    return {
        "updated": updated_count,
        "skipped": skipped_count,
        "total": len(tokens),
    }


if __name__ == "__main__":
    result = sync_model_limits()
    print(json.dumps(result, indent=2, ensure_ascii=False))
