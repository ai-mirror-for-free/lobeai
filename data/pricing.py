import json
import requests
import pandas as pd


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
        print(f"Error fetching pricing: {e}")
        return None


if __name__ == "__main__":
    # Example usage:
    model_list = [
        "anthropic/claude-3.5-haiku",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.7-sonnet",
        "anthropic/claude-3.7-sonnet:thinking",
        "anthropic/claude-3-haiku",
        "anthropic/claude-haiku-4.5",
        "anthropic/claude-opus-4",
        "anthropic/claude-opus-4.1",
        "anthropic/claude-opus-4.5",
        "anthropic/claude-opus-4.6",
        "anthropic/claude-sonnet-4.6",
        "google/gemini-2.0-flash-001",
        "google/gemini-2.0-flash-lite-001",
        "google/gemini-2.5-flash",
        "google/gemini-2.5-flash-lite-preview-09-2025",
        "google/gemini-2.5-pro-preview",
        "google/gemini-3.1-flash-image-preview",
        "google/gemini-3.1-flash-lite-preview",
        "google/gemini-3.1-pro-preview",
        "google/gemini-3-flash-preview",
        "google/gemini-3-pro-preview",
        "google/gemma-3-27b-it",
        "google/gemma-3-4b-it",
        "google/gemma-3n-e2b-it:free",
        "google/gemma-3n-e4b-it",
        "openai/gpt-3.5-turbo-0613",
        "openai/gpt-4.1",
        "openai/gpt-4.1-mini",
        "openai/gpt-4o-mini",
        "openai/gpt-4-turbo",
        "openai/gpt-5.1-codex",
        "openai/gpt-5.1",
        "openai/gpt-5.4",
        "openai/gpt-5-image",
        "openai/gpt-5-mini",
        "openai/gpt-5-nano",
        "openai/gpt-oss-120b",
        "openai/o3",
        "openai/o3-mini",
        "openai/o3-mini-high",
    ]
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
        if pricing:
            print(f"Model: {model} Pricing: {pricing}")
            pricing_data[model] = pricing
            pricing_db = pd.concat(
                [
                    pricing_db,
                    pd.DataFrame(
                        [
                            {
                                "model": model,
                                "prompt": pricing.get("prompt", None),
                                "completion": pricing.get("completion", None),
                                "image": pricing.get("image", None),
                                "audio": pricing.get("audio", None),
                                "internal_reasoning": pricing.get(
                                    "internal_reasoning", None
                                ),
                                "input_cache_read": pricing.get(
                                    "input_cache_read", None
                                ),
                                "input_cache_write": pricing.get(
                                    "input_cache_write", None
                                ),
                                "web_search": pricing.get("web_search", None),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    if pricing_data:
        pricing_db.to_csv("data/pricing_db.csv", index=False)
        with open("data/pricing_data.json", "w") as f:
            json.dump(pricing_data, f, indent=4)
