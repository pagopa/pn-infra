import pytest

import processor.input_loader as input_loader


@pytest.fixture(autouse=True)
def reset_input_loader_cache():
    input_loader._manifest_cache = None
    input_loader._table_config_cache = {}

    yield

    input_loader._manifest_cache = None
    input_loader._table_config_cache = {}
