"""
体验接口服务
输入用户 key、模型、文本，调用 new-api 并返回结果
对于 image 模型，提取并返回图片
"""
import json
import base64
import os
import re
import requests
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file="experience_api.log")

# 图片模型列表（与 api.json 中 image 套餐一致）
IMAGE_MODELS = {
    "openai/gpt-5.4-image-2",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
}

# new-api 的 base URL（直接调用后端）
NEWAPI_BASE = os.getenv("NEWAPI_URL", "http://154.64.231.128:25142")


def is_image_model(model: str) -> bool:
    """判断是否为图片模型"""
    # 完全匹配
    if model in IMAGE_MODELS:
        return True
    # 模糊匹配：包含 image 关键字
    if "image" in model.lower():
        return True
    return False


def _extract_image_from_response(data: dict) -> dict:
    """
    从 new-api 返回的 JSON 中提取图片
    返回 { "type": "image", "image_base64": "...", "format": "png" }
    """
    choices = data.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})
    content = message.get("content") or ""

    # 1. 先看 images 数组 (new-api 格式)
    images_data = message.get("images", [])
    if images_data and isinstance(images_data, list):
        for img_item in images_data:
            url = None
            if isinstance(img_item, dict):
                img_url_obj = img_item.get("image_url", {})
                if isinstance(img_url_obj, dict):
                    url = img_url_obj.get("url", "")
                elif isinstance(img_url_obj, str):
                    url = img_url_obj
            elif isinstance(img_item, str):
                url = img_item

            if url and url.startswith("data:image"):
                b64 = url.split(",", 1)[1]
                # 提取格式
                fmt_match = re.search(r'data:image/(\w+)', url)
                fmt = fmt_match.group(1) if fmt_match else "png"
                return {
                    "type": "image",
                    "image_base64": b64,
                    "format": fmt,
                }

    # 2. Markdown 图片格式: ![xxx](data:image/png;base64,...)
    md_match = re.search(r'!\[.*?\]\((data:image/(\w+);base64,([^)]+))\)', content)
    if md_match:
        return {
            "type": "image",
            "image_base64": md_match.group(3),
            "format": md_match.group(2),
        }

    # 3. 纯 base64 的 content
    try:
        base64.b64decode(content)
        return {
            "type": "image",
            "image_base64": content,
            "format": "png",
        }
    except Exception:
        pass

    return None


def call_experience(key: str, model: str, text: str) -> dict:
    """
    调用体验接口

    Args:
        key: 用户 API key
        model: 模型名称
        text: 用户输入文本

    Returns:
        {
            "status": True,
            "type": "text" | "image",
            "content": "对话文本" | None,
            "image_base64": "base64..." | None,
            "format": "png" | None,
            "model": "模型名"
        }
    """
    url = f"{NEWAPI_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "stream": False,
    }

    try:
        logger.info(f"体验接口请求: model={model}")
        resp = requests.post(url, headers=headers, json=payload, timeout=300)
        elapsed = resp.elapsed.total_seconds()

        if resp.status_code != 200:
            error_body = ""
            try:
                error_body = resp.json()
            except Exception:
                error_body = resp.text[:500]
            logger.error(f"体验接口返回错误: {resp.status_code} {error_body}")
            return {
                "status": False,
                "error": f"API 返回错误 ({resp.status_code})",
                "detail": error_body,
            }

        data = resp.json()

        # 判断是否为图片模型
        if is_image_model(model):
            img_result = _extract_image_from_response(data)
            if img_result:
                logger.info(f"体验接口成功: image, 耗时 {elapsed:.2f}s")
                return {
                    "status": True,
                    "type": "image",
                    "image_base64": img_result["image_base64"],
                    "format": img_result["format"],
                    "model": model,
                    "elapsed": elapsed,
                }
            # 图片模型但没提取到图片，退回到文本
            logger.warning(f"图片模型但未提取到图片，退回文本: {model}")

        # 文本响应
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "") or ""
            logger.info(f"体验接口成功: text, 耗时 {elapsed:.2f}s")
            return {
                "status": True,
                "type": "text",
                "content": content,
                "model": model,
                "elapsed": elapsed,
            }

        return {
            "status": False,
            "error": "响应中没有 choices",
            "detail": data,
        }

    except requests.exceptions.Timeout:
        logger.error("体验接口请求超时")
        return {"status": False, "error": "请求超时（300 秒）"}
    except Exception as e:
        logger.error(f"体验接口异常: {e}")
        return {"status": False, "error": str(e)}
