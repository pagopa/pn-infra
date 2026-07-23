import os
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config"
)

CONFIG_PATH = Path(
    os.environ.get("CONFIG_PATH", str(DEFAULT_CONFIG_PATH))
)

MANIFEST_PATH = CONFIG_PATH / "manifest.yaml"

_manifest_cache = None
_table_config_cache = {}


def _load_yaml(file_path):
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file)

    if not isinstance(content, dict):
        raise ValueError(
            f"Invalid YAML configuration: {file_path}"
        )

    return content


def load_manifest():
    global _manifest_cache

    if _manifest_cache is None:
        _manifest_cache = _load_yaml(MANIFEST_PATH)

    return _manifest_cache


def load_table_config(table_name):
    if not table_name:
        return None

    if table_name in _table_config_cache:
        return _table_config_cache[table_name]

    manifest = load_manifest()
    table_entry = manifest.get("tables", {}).get(table_name)

    if not table_entry:
        return None

    if not table_entry.get("enabled", True):
        return None

    config_file = table_entry.get("config")

    if not config_file:
        raise ValueError(
            f"Missing configuration path for table: {table_name}"
        )

    config_path = CONFIG_PATH / config_file
    table_config = _load_yaml(config_path)

    configured_table = table_config.get("table")

    if configured_table and configured_table != table_name:
        raise ValueError(
            f"Configuration table mismatch: expected {table_name}, "
            f"found {configured_table}"
        )

    _table_config_cache[table_name] = table_config

    return table_config