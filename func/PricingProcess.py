import json
import os
import pandas as pd
from tools.LoggerManager import LoggerManager

logger = LoggerManager(log_file='pricing_process.log')
data = pd.read_csv("data/pricing_plan.csv")
model_list = data["model"].to_list()

# 套餐价格（元/天）
PLAN_PRICES = {
    "free": 0,
    "default": 1,
    "vip": 2,
    "svip": 4,
}

def fill_pricing_plan(update=False):
    json_path = "data/pricing_plan.json"
    if update:
        if os.path.exists(json_path):
            os.remove(json_path)
        csv_columns = [col for col in data.columns if col != "model"]
        # 初始化所有 plan
        pricing_plan = {plan: {"modele_list": [], "price": PLAN_PRICES.get(plan, 1)} for plan in csv_columns}

        # 根据 CSV 数据填充模型列表
        for model in model_list:
            for plan_name in csv_columns:
                if data[data["model"] == model][plan_name].values[0]:
                    pricing_plan[plan_name]["modele_list"].append(model)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pricing_plan, f, indent=4)
        logger.info(f"填充 pricing_plan.json 文件成功")
    else:
        with open(json_path, "r", encoding="utf-8") as f:
            pricing_plan = json.load(f)
        # 确保所有 plan 都有 price 字段
        for plan, info in pricing_plan.items():
            if "price" not in info:
                info["price"] = PLAN_PRICES.get(plan, 1)
    return pricing_plan


if __name__ == "__main__":
    fill_pricing_plan(True)
