import pytest

import processor.input_loader as input_loader


@pytest.fixture(autouse=True)
def reset_input_loader_cache():
    input_loader._manifest_cache = None
    input_loader._table_config_cache = {}

    yield

    input_loader._manifest_cache = None
    input_loader._table_config_cache = {}


@pytest.fixture
def temp_config_env(tmp_path, monkeypatch):
    config_path = tmp_path / "config"
    manifest_path = config_path / "manifest.yaml"

    monkeypatch.setattr(input_loader, "CONFIG_PATH", config_path)
    monkeypatch.setattr(input_loader, "MANIFEST_PATH", manifest_path)

    return config_path, manifest_path
