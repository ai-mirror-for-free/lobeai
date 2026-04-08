"""
同步 NewAPI 令牌模型限制和 OpenWebUI 设置

当 data/pricing_plan.csv 发生变化后，执行此脚本同步更新：
1. 从 fill_pricing_plan 获取最新套餐模型列表
2. 查询 NewAPI 数据库中需要同步的用户令牌
3. 检查并更新 token 的 model_limits
4. 同步更新 OpenWebUI 的 settings
"""

import json
from tools.DbScript import NewApiDatabaseManager, OpenWebUIDatabaseManager
from tools.LoggerManager import LoggerManager
from func.PricingProcess import fill_pricing_plan

logger = LoggerManager(log_file="sync_model_limits.log")
newapidata = NewApiDatabaseManager()
openwebuidata = OpenWebUIDatabaseManager()

EXCLUDED_NAME = "local"
EXCLUDED_GROUP = "free"


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


def _get_user_email_from_token_name(token_name: str) -> str:
    """
    从令牌名称推导用户邮箱
    根据 CreaterUsers.py，令牌名称就是用户的 email
    """
    return token_name


def _build_openwebui_settings(token_key: str, model_limits: list) -> str:
    """
    构建 OpenWebUI settings JSON 字符串
    参考 CreaterUsers.py 的 settings 格式
    """
    setting = {
        "ui": {
            "version": "0.8.10",
            "directConnections": {
                "OPENAI_API_BASE_URLS": ["https://api.chat-keeper.com/v1"],
                "OPENAI_API_KEYS": [token_key],
                "OPENAI_API_CONFIGS": {
                    "0": {
                        "enable": True,
                        "tags": [],
                        "prefix_id": "  ",
                        "model_ids": model_limits,
                        "connection_type": "external",
                        "auth_type": "bearer",
                    }
                },
            },
        }
    }
    return json.dumps(setting)


def _determine_plan_level(token_name: str, token_group: str) -> str:
    """
    根据令牌信息推断套餐级别
    group 字段对应套餐级别: free, default, vip, svip
    """
    if token_group and token_group != "":
        return token_group
    # 如果 group 为空，尝试从名称推断（备用逻辑）
    return "default"


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


def _update_openwebui_settings(email: str, settings: str) -> bool:
    """更新 OpenWebUI 用户设置"""
    openwebuidata.connect()
    result = openwebuidata.execute_command(
        'UPDATE "user" SET settings = %s WHERE email = %s',
        (settings, email)
    )
    openwebuidata.disconnect()
    return result


def sync_model_limits():
    """
    主同步流程
    """
    # Step 1: 获取最新套餐列表
    pricing_plan = fill_pricing_plan()
    logger.info(f"加载定价计划: {list(pricing_plan.keys())}")

    # Step 2: 查询所有需要同步的令牌
    tokens = _get_all_tokens_from_db()
    logger.info(f"从数据库获取到 {len(tokens)} 个令牌")

    updated_count = 0
    skipped_count = 0

    for token_row in tokens:
        token_id, token_key, token_name, status, remain_quota, \
            unlimited_quota, model_limits_enabled, model_limits, token_group = token_row

        # Step 3: 过滤排除项
        if token_name == EXCLUDED_NAME:
            logger.info(f"跳过排除的令牌: {token_name}")
            skipped_count += 1
            continue
        if token_group == EXCLUDED_GROUP:
            logger.info(f"跳过 free 分组令牌: {token_name}")
            skipped_count += 1
            continue

        # Step 4: 推断套餐级别
        plan_level = _determine_plan_level(token_name, token_group)

        # 查找对应的套餐列表
        if plan_level not in pricing_plan:
            logger.warning(f"令牌 {token_name} 的套餐级别 {plan_level} 不在定价计划中，跳过")
            skipped_count += 1
            continue

        expected_models = pricing_plan[plan_level]["modele_list"]
        current_models = _parse_model_limits(model_limits)

        # Step 5: 检查是否需要更新
        if _list_equals(current_models, expected_models):
            logger.info(f"令牌 {token_name} (套餐: {plan_level}) 模型列表无需更新")
            skipped_count += 1
            continue

        logger.info(
            f"令牌 {token_name} (套餐: {plan_level}) 模型列表不一致，需要更新:"
        )
        logger.info(f"  当前: {current_models}")
        logger.info(f"  期望: {expected_models}")

        # Step 6: 更新 NewAPI token model_limits
        new_model_limits = ",".join(expected_models)
        if _update_token_model_limits(token_id, new_model_limits):
            logger.info(f"  -> NewAPI token model_limits 已更新")
        else:
            logger.error(f"  -> NewAPI token model_limits 更新失败")
            continue

        # Step 7: 更新 OpenWebUI settings
        email = _get_user_email_from_token_name(token_name)
        settings = _build_openwebui_settings(token_key, expected_models)
        if _update_openwebui_settings(email, settings):
            logger.info(f"  -> OpenWebUI settings 已更新")
        else:
            logger.error(f"  -> OpenWebUI settings 更新失败")
            continue

        updated_count += 1

    logger.info(f"同步完成: 更新 {updated_count} 个令牌, 跳过 {skipped_count} 个")
    return {
        "updated": updated_count,
        "skipped": skipped_count,
        "total": len(tokens),
    }


if __name__ == "__main__":
    result = sync_model_limits()
    print(json.dumps(result, indent=2, ensure_ascii=False))
