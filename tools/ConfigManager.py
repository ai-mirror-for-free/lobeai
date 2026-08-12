"""
统一配置加载器（对齐 claude_agent 的 config/__init__.py 模式）

- 非密钥配置读 config/config.yaml（正式）或 config/config_{ENV}.yaml（如 ENV=dev）
- 密钥类（*_PASSWORD_ENCRYPTED / ENCRYPTION_KEY）只从 .env / os.environ 读取，不进 yaml
- 读取优先级：os.environ > yaml（保证 .env 或进程注入能覆盖 yaml）

用法:
    from tools.ConfigManager import get_env
    url = get_env("NEWAPI_URL", "http://localhost:25142")
    admin_user = get_env("ADMIN_USERNAME")

独立脚本直接运行（python func/SyncApiJson.py）也能正常读取，
因为 ConfigManager 用 __file__ 相对定位项目根，不依赖 cwd。
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录（tools/ 的父目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_ENV_FILE = _PROJECT_ROOT / ".env"

# 启动时加载 .env，确保 ENV 等变量可被读取（claude_agent 的 ConfigLoader 同样先 load_dotenv）
# load_dotenv 默认不覆盖已存在的环境变量，进程注入优先级更高
load_dotenv(_ENV_FILE)

# 非密钥配置项 -> yaml 路径映射
# 密钥类（ADMIN_PASSWORD_ENCRYPTED / DB_PASSWORD_ENCRYPTED / NEWAPI_PASSWORD_ENCRYPTED /
# ENCRYPTION_KEY）刻意不在此表，只允许从 os.environ 读取。
_ENV_TO_YAML_PATH = {
    "ADMIN_USERNAME": "admin.username",
    "ADMIN_EMAIL": "admin.email",
    "DB_HOST": "database.host",
    "DB_PORT": "database.port",
    "DB_USERNAME": "database.username",
    "NEWAPI_URL": "newapi.url",
    "NEWAPI_USER": "newapi.username",
    "SERVER_B_URL": "server_b.url",
}

_cache: dict | None = None


def _load_yaml() -> dict:
    """按 ENV 加载 config_{ENV}.yaml，无 ENV 或文件缺失回退 config.yaml"""
    global _cache
    if _cache is not None:
        return _cache

    env = os.getenv("ENV", "").strip()
    config_file = _CONFIG_DIR / "config.yaml"
    if env:
        env_file = _CONFIG_DIR / f"config_{env}.yaml"
        if env_file.exists():
            config_file = env_file

    with open(config_file, "r", encoding="utf-8") as f:
        _cache = yaml.safe_load(f) or {}
    return _cache


def _get_yaml(path: str, default=None):
    """按点分路径读取 yaml 值，如 'server_b.url'"""
    value = _load_yaml()
    for key in path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default


def get_env(key: str, default=None):
    """统一读取配置：os.environ 优先，其次 yaml（仅限非密钥项）"""
    # 1. 环境变量优先（.env 或进程注入）
    if key in os.environ and os.environ.get(key) != "":
        return os.environ.get(key)
    # 2. 非密钥项回退 yaml
    if key in _ENV_TO_YAML_PATH:
        return _get_yaml(_ENV_TO_YAML_PATH[key], default)
    # 3. 未知项（密钥类等）只认 env，无则返回默认
    return default


def clear_cache():
    """清除 yaml 缓存（测试用；正常进程生命周期内配置不变）"""
    global _cache
    _cache = None
