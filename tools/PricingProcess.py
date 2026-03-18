import json
import requests
import pandas as pd
from tools.DbScript import NewApiDatabaseManager
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file='pricing_process.log')
db = NewApiDatabaseManager()
data = pd.read_excel("data/pricing_plan.xlsx")
model_list = data["model"].to_list()

def fill_pricing_plan(): 
    # 套餐价格
    pricing_plan = {
        "free": {"price": 0, "modele_list": []},
        "basic": {"price": 29, "modele_list": []},
        "pro": {"price": 49, "modele_list": []},
        "enterprise": {"price": 99, "modele_list": []},
    }
    for model in model_list:
        for plan_name, plan_data in pricing_plan.items():
            if not int(data[data["model"] == model][plan_name].values[0]):
                continue
            pricing_plan[plan_name]["modele_list"].append(model)
    return pricing_plan

PRICING_PLAN = fill_pricing_plan()

def get_model_pricing(model_id: str):
    """
    Fetches the input and output pricing for a specific model from OpenRouter.

    Args:
        model_id (str): The ID of the model (e.g., 'openai/gpt-4o').

    Returns:
        dict: A dictionary containing 'prompt_price' and 'completion_price' as floats,
              or None if the model is not found or an error occurs.
    """
    url = "https://openrouter.ai/api/v1/models"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # OpenRouter data structure is in 'data' list
        models = data.get("data", [])

        for model in models:
            if model["id"] == model_id:
                pricing = model.get("pricing", {})
                pricing = {
                    k: float(v) * 1e6 for k, v in pricing.items() if v is not None
                }
                pricing["web_search"] = (
                    pricing.get("web_search", 0) / 1000
                    if pricing.get("web_search", 0)
                    else None
                )
                return pricing
        return None

    except Exception as e:
        logger.error(f"Error fetching pricing: {e}")
        return None


def get_newest_pricing():
    pricing_data = {}
    pricing_db = pd.DataFrame(
        columns=[
            "model",
            "prompt",
            "completion",
            "image",
            "audio",
            "internal_reasoning",
            "input_cache_read",
            "input_cache_write",
            "web_search",
        ]
    )
    for model in model_list:
        pricing = get_model_pricing(model)
        if not pricing:
            continue
        logger.info(f"Model: {model} Pricing: {pricing}")
        pricing_data[model] = pricing
        temp = pd.DataFrame(
            [
                {
                    "model": model,
                    "prompt": pricing.get("prompt", None),
                    "completion": pricing.get("completion", None),
                    "image": pricing.get("image", None),
                    "audio": pricing.get("audio", None),
                    "internal_reasoning": pricing.get("internal_reasoning", None),
                    "input_cache_read": pricing.get("input_cache_read", None),
                    "input_cache_write": pricing.get("input_cache_write", None),
                    "web_search": pricing.get("web_search", None),
                }
            ]
        )
        pricing_db = pd.concat([pricing_db, temp], ignore_index=True)
    if pricing_data:
        pricing_db.to_csv("data/pricing_db.csv", index=False)
    return pricing_data


def upfdate_model_pricing(ratio=1):
    newest_pricing = get_newest_pricing()
    db.connect()
    # 获取当前 价格
    model_option = db.execute_query("select * from options")
    model_option = {
        option[0]: option[1] for option in model_option
    }
    # 输入价格
    ModelRatio = json.loads(model_option['ModelRatio'])
    # 补全价格
    CompletionRatio = json.loads(model_option['CompletionRatio'])
    # 缓存读取价格
    CacheRatio = json.loads(model_option['CacheRatio'])
    # 缓存创建价格
    CreateCacheRatio = json.loads(model_option['CreateCacheRatio'])
    # 图片输入价格
    ImageRatio = json.loads(model_option['ImageRatio'])
    # 音频输入价格
    AudioRatio = json.loads(model_option['AudioRatio'])
    # 音频补全价格
    AudioCompletionRatio = json.loads(model_option['AudioCompletionRatio'])

    need_update = {
        "ModelRatio":False,
        "CompletionRatio":False,
        "CacheRatio":False,
        "CreateCacheRatio":False,
        "ImageRatio":False,
        "AudioRatio":False,
        "AudioCompletionRatio":False
    }

    for model in model_list:
        if model not in newest_pricing:
            print(f"Model: {model} not found in newest_pricing, skipping")
            continue
        model_price = newest_pricing[model]
        # 输入价格
        if model_price.get("prompt"):
            need_update["ModelRatio"] = True
            ModelRatio[model] = model_price.get("prompt")*ratio
        # 补全价格
        if model_price.get("completion"):
            need_update["CompletionRatio"] = True
            CompletionRatio[model] = model_price.get("completion")*ratio
        # 图片输入价格
        if model_price.get("image"):
            need_update["ImageRatio"] = True
            ImageRatio[model] = model_price.get("image")*ratio
        # 音频输入价格+音频补全价格
        if model_price.get("audio"):
            need_update["AudioRatio"] = True
            AudioRatio[model] = model_price.get("audio")*ratio
            AudioCompletionRatio[model] = model_price.get("audio")*ratio
        # 缓存读取价格
        if model_price.get("input_cache_read"):
            need_update["CacheRatio"] = True
            CacheRatio[model] = model_price.get("input_cache_read")*ratio
        # 缓存创建价格
        if model_price.get("input_cache_write"):
            need_update["CreateCacheRatio"] = True
            CreateCacheRatio[model] = model_price.get("input_cache_write")*ratio
    model_option['ModelRatio'] = json.dumps(ModelRatio)
    model_option['CompletionRatio'] = json.dumps(CompletionRatio)
    model_option['CacheRatio'] = json.dumps(CacheRatio)
    model_option['CreateCacheRatio'] = json.dumps(CreateCacheRatio)
    model_option['ImageRatio'] = json.dumps(ImageRatio)
    model_option['AudioRatio'] = json.dumps(AudioRatio)
    model_option['AudioCompletionRatio'] = json.dumps(AudioCompletionRatio)
    for key in need_update:
        if need_update[key]:
            logger.info(f"table options {key} update to {model_option[key]}")
            db.execute_command(
                f"update options set value = '{model_option[key]}' where key = '{key}'"
            )
    db.disconnect()


if __name__ == "__main__":
    upfdate_model_pricing()
