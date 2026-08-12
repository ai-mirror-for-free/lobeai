"""
同步 NewAPI 渠道模型到 data/api.json

从 new-api 的 OpenRouter (type=20) 与 Vertex AI (type=41) 两个渠道
读取全部已配置模型（仅 status=1 启用的渠道），合并去重后更新 api.json：
- image 组原样保留，不参与任何变更
- chat 组 = 两渠道模型并集 − image 组已有模型

用法:
    python -m func.SyncApiJson            # 单独运行（在 lobeai 根目录）
    python func/SyncApiJson.py            # 直接运行
    或由 func/SyncModelLimits.py 启动时自动调用

渠道 type 说明（见 new-api constant/channel.go）:
    ChannelTypeOpenRouter = 20
    ChannelTypeVertexAi   = 41
"""

import json
import sys
from pathlib import Path

# 支持以脚本方式直接运行: python func/SyncApiJson.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.DbScript import NewApiDatabaseManager
from tools.LoadApiConfig import load_api_config, clear_cache
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file="sync_api_json.log")

# 参与同步的渠道 type 列表
CHANNEL_TYPES = [20, 41]  # OpenRouter, VertexAI
CHANNEL_TYPE_NAMES = {20: "OpenRouter", 41: "VertexAI"}

# api.json 路径（基于本文件相对定位，避免写死绝对路径）
_API_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "api.json"


def get_channel_models(db) -> set:
    """查询指定 type 的启用渠道 (status=1)，合并所有 models 字段为 set"""
    merged = set()
    db.connect()
    try:
        for ct in CHANNEL_TYPES:
            rows = db.execute_query(
                "SELECT name, models FROM channels WHERE type = %s AND status = 1",
                (ct,),
            )
            if not rows:
                logger.warning(f"渠道 type={ct} ({CHANNEL_TYPE_NAMES.get(ct)}) 未查询到启用渠道")
                continue
            for name, models in rows:
                if not models:
                    continue
                for m in models.split(","):
                    m = m.strip()
                    if m:
                        merged.add(m)
            logger.info(f"渠道 type={ct} ({CHANNEL_TYPE_NAMES.get(ct)}) 累计模型 {len(merged)} 个")
    finally:
        db.disconnect()
    return merged


def sync_api_json() -> dict:
    """
    同步并写回 api.json，返回变更 diff

    Returns:
        {
            "chat_added": [...],      # chat 组本次新增的模型
            "chat_removed": [...],    # chat 组本次移除的模型
            "image_models": [...],    # image 组（原样保留）
        }

    Raises:
        RuntimeError: 未获取到任何渠道模型时抛出（防止误清空 api.json）
    """
    db = NewApiDatabaseManager()
    channel_models = get_channel_models(db)

    if not channel_models:
        raise RuntimeError("未从 new-api 渠道获取到任何模型，中止写入以防清空 api.json")

    # 读取当前 api.json（image 组保留）
    current = load_api_config()
    old_chat = list(current.get("chat", []))
    image_models = list(current.get("image", []))

    # chat = 渠道模型并集 − image 组已有模型；image 原样保留
    new_chat = sorted(channel_models - set(image_models))
    new_image = image_models

    with open(_API_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"chat": new_chat, "image": new_image}, f, ensure_ascii=False, indent=4)

    # 失效 LoadApiConfig 缓存，避免同进程后续读到旧数据
    clear_cache()

    diff = {
        "chat_added": sorted(set(new_chat) - set(old_chat)),
        "chat_removed": sorted(set(old_chat) - set(new_chat)),
        "image_models": new_image,
    }
    logger.info(f"api.json 同步完成: 新增 {len(diff['chat_added'])} 个, 移除 {len(diff['chat_removed'])} 个")
    return diff


if __name__ == "__main__":
    try:
        result = sync_api_json()
    except Exception as e:
        logger.error(f"同步失败: {e}")
        print(json.dumps({"status": False, "error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps({"status": True, **result}, ensure_ascii=False, indent=2))
