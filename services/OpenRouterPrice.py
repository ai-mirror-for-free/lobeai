"""
OpenRouter 模型价格查询服务
"""
import requests
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def get_all_models() -> List[Dict[str, Any]]:
    """
    获取 OpenRouter 所有模型列表

    Returns:
        模型列表
    """
    try:
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', [])
    except Exception as e:
        logger.error(f"获取 OpenRouter 模型列表失败: {e}")
        return []


def search_models(query: str, all_models: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    搜索模型

    Args:
        query: 搜索关键词
        all_models: 可选的预缓存模型列表

    Returns:
        匹配的模型列表
    """
    if all_models is None:
        all_models = get_all_models()

    if not query or not query.strip():
        # 无关键词时返回最热门的模型（按价格排序）
        return sort_by_popularity(all_models)[:20]

    query_lower = query.lower().strip()

    # 搜索匹配
    results = [
        m for m in all_models
        if query_lower in m.get('id', '').lower()
        or query_lower in m.get('name', '').lower()
    ]

    # 按价格从低到高排序
    results.sort(key=lambda x: float(x.get('pricing', {}).get('prompt', 0)))

    return results[:20]


def sort_by_popularity(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按流行度排序（简单实现：优先显示有 context_length 较大的模型）
    """
    return sorted(
        models,
        key=lambda x: (
            float(x.get('pricing', {}).get('prompt', 0)) * 1000
            - int(x.get('context_length', 0)) / 1000
        )
    )


def format_price(price: float) -> str:
    """
    格式化价格显示

    Args:
        price: 每 token 价格（美元）

    Returns:
        格式化后的价格字符串
    """
    if price == 0:
        return "免费"

    # 转换为每 1M tokens 的价格
    price_per_million = price * 1_000_000

    if price_per_million < 0.01:
        return f"${price_per_million:.6f}/1M"
    elif price_per_million < 1:
        return f"${price_per_million:.4f}/1M"
    else:
        return f"${price_per_million:.2f}/1M"


def format_model_info(model: Dict[str, Any]) -> Dict[str, Any]:
    """
    格式化模型信息，只返回需要显示的字段

    Args:
        model: 原始模型数据

    Returns:
        格式化后的模型信息
    """
    pricing = model.get('pricing', {})
    context_length = model.get('context_length', 0)
    pricing_length = model.get('pricing_length', context_length)

    return {
        'id': model.get('id', ''),
        'name': model.get('name', model.get('id', '')),
        'prompt_price': format_price(float(pricing.get('prompt', 0))),
        'completion_price': format_price(float(pricing.get('completion', 0))),
        'prompt_price_raw': float(pricing.get('prompt', 0)),
        'completion_price_raw': float(pricing.get('completion', 0)),
        'context_length': context_length,
        'pricing_length': pricing_length,
        'context_display': f"{context_length:,}" if context_length else "N/A",
    }
