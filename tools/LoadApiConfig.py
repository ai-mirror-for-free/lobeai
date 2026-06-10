"""
统一的 api.json 加载工具
所有需要读取 data/api.json 的地方都通过此函数
"""
import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "api.json")
_cache = None


def load_api_config() -> dict:
    """
    加载 api.json，带缓存（避免重复读文件）

    Returns:
        api.json 的完整 dict，如 {"chat": [...], "image": [...]}
    """
    global _cache
    if _cache is not None:
        return _cache

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        _cache = json.load(f)
    return _cache


def get_image_models() -> set:
    """
    获取所有图片模型列表（来自 api.json 中 image 套餐）

    Returns:
        图片模型名的 set
    """
    config = load_api_config()
    models = config.get("image", [])
    return set(models)
