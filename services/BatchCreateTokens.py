import json
import time
import os
from tools.GetNewestRate import get_usd_cny_rate
from tools.LoadApiConfig import load_api_config
from tools.LoggerManager import LoggerManager
from services.NewAPIClient import NewAPIClient, TokenConfig

logger = LoggerManager(log_file="batch_create_tokens.log")
# 追加到所有套餐模型列表后的额外模型（修改后需重启服务生效）
extra_modellist: list[str] = ['openai/gpt-4o-mini', 'openai/gpt-4o']


def batch_create_tokens(
    n: int,
    package: str,
    price: float,
    admin_client: NewAPIClient,
) -> list | dict:
    """
    批量创建 NewAPI 令牌

    Args:
        n: 创建令牌数量
        package: 套餐类型 key（如 chat, image）
        price: 总价（人民币，额度计算时通过汇率转为美元）
        admin_client: 已认证的 NewAPIClient 实例（由 Depends 注入）

    Returns:
        成功时返回纯列表，每项为格式化消息字符串
        失败时返回 {"status": False, "error": "..."}
        部分失败时返回 {"status": "partial", "tokens": [...], "errors": [...]}
    """
    # ---------------------------------------------------------------
    # Step 1: 加载套餐定义并校验 package key
    # ---------------------------------------------------------------
    try:
        api_data = load_api_config()
    except Exception as e:
        logger.error(f"无法加载 api.json: {e}")
        return {"status": False, "error": f"无法加载模型列表配置文件: {e}"}

    if package not in api_data:
        valid_keys = list(api_data.keys())
        logger.error(f"无效的套餐类型: {package}，有效值为: {valid_keys}")
        return {
            "status": False,
            "error": f"无效的套餐类型: {package}，有效值为: {', '.join(valid_keys)}",
        }

    model_list = api_data[package]
    # 拷贝后追加，避免原地修改 api.json 的全局缓存（load_api_config 是带缓存的单例）
    model_list = model_list + extra_modellist
    model_limits_str = ",".join(model_list)

    # ---------------------------------------------------------------
    # Step 2: 获取汇率并计算额度
    # ---------------------------------------------------------------
    rate, local = get_usd_cny_rate()
    if not local:
        logger.warning("汇率获取失败，使用缓存汇率")

    # price 为人民币总价，price / rate 将人民币转为美元，再乘系数得到额度
    remain_quota = int(price / rate * 500000)

    # ---------------------------------------------------------------
    # Step 3: 循环创建 n 个令牌（永不过期）
    # ---------------------------------------------------------------
    created_tokens = []
    errors = []
    timestamp = int(time.time())

    for i in range(1, n + 1):
        token_name = f"batch-{package}-{timestamp}-{i}"
        try:
            token_data = admin_client.create_token(
                TokenConfig(
                    name=token_name,
                    remain_quota=remain_quota,
                    expired_time=-1,           # 永不过期
                    unlimited_quota=False,
                    model_limits_enabled=True,
                    model_limits=model_limits_str,
                    group="api",
                )
            )
            token_key = token_data.get("key")
            if not token_key or token_key == "***":
                raise RuntimeError("无法获取有效的 token key")

            base_url = "https://image.chat-keeper.com" if package == "image" else "https://api.chat-keeper.com"
            formatted = (
                f"欢迎使用您在chat-keeper购买api\n"
                f"base_url: {base_url}\n"
                f"api_key为{token_key}  \n"
                f"您购买的套餐类型为{package}\n"
                f"价格为{price}元\n"
                f"可使用如下模型{model_limits_str}\n"
            )
            created_tokens.append(formatted)
            logger.info(f"已创建令牌 #{i}: {token_name}")

        except RuntimeError as e:
            error_msg = f"创建令牌 #{i} ({token_name}) 失败: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            # 继续创建剩余令牌，不中断批次
            continue

    # ---------------------------------------------------------------
    # Step 5: 组装返回结果
    # ---------------------------------------------------------------
    if errors:
        # 部分或全部失败
        if not created_tokens:
            return {"status": False, "error": "所有令牌创建失败", "details": errors}
        return {"status": "partial", "tokens": created_tokens, "errors": errors}

    # 全部成功，返回纯列表
    return created_tokens
