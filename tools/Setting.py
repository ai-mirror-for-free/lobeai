def get_setting(token_key, model_limits):
    setting = {
        "ui": {
            "version": "0.9.1",
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
            "system": "CURRENT_DATETIME: {{CURRENT_DATETIME}}",
            "params": {},
        }
    }
    return setting
