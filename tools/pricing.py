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
                pricing["web_search"] = pricing.get("web_search", 0) / 1000
                return pricing
        return None

    except Exception as e:
        print(f"Error fetching pricing: {e}")
        return None


if __name__ == "__main__":
    # Example usage:
    model_list = [
        "anthropic/claude-3.7-sonnet:thinking",
        "anthropic/claude-3-haiku",
        "anthropic/claude-opus-4.1",
        "anthropic/claude-opus-4",
        "anthropic/claude-3.7-sonnet",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-opus-4.5",
        "anthropic/claude-3.5-haiku",
        "anthropic/claude-opus-4.6",
        "google/gemma-3n-e2b-it:free",
        "google/gemma-3-4b-it",
        "google/gemini-3-pro-preview",
        "google/gemini-2.5-pro-preview",
        "google/gemma-3-27b-it",
        "google/gemini-3-flash-preview",
        "google/gemma-3n-e4b-it",
        "google/gemini-2.0-flash-001",
        "google/gemini-2.5-flash-lite-preview-09-2025",
        "google/gemini-3.1-flash-image-preview",
        "openai/gpt-5-mini",
        "openai/o3",
        "openai/gpt-4o-mini",
        "openai/gpt-5-image",
        "openai/o3-mini",
        "openai/o3-mini-high",
        "openai/gpt-4.1",
        "openai/gpt-5.1-codex",
        "openai/gpt-3.5-turbo-0613",
        "openai/gpt-4-turbo",
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
            "web_search"
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
                                "prompt": pricing.get("prompt", 0),
                                "completion": pricing.get("completion", 0),
                                "image": pricing.get("image", 0),
                                "audio": pricing.get("audio", 0),
                                "internal_reasoning": pricing.get("internal_reasoning", 0),
                                "input_cache_read": pricing.get("input_cache_read", 0),
                                "input_cache_write": pricing.get("input_cache_write", 0),
                                "web_search": pricing.get("web_search", 0),
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
