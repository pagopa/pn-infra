import pytest
import yaml

from processor.input_loader import load_manifest, load_table_config


def _write_yaml(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as yaml_file:
        yaml.safe_dump(content, yaml_file)


def _write_manifest(manifest_path, table_name, config_file=None, enabled=True):
    entry = {"enabled": enabled}

    if config_file is not None:
        entry["config"] = config_file

    _write_yaml(manifest_path, {"tables": {table_name: entry}})


# Verify that None is returned for a falsy table name, an unknown table, or a
# table not present in the manifest.
@pytest.mark.parametrize(
    "table_name",
    [
        pytest.param(None, id="falsy-table-name"),
        pytest.param("", id="falsy-table-name-empty-string"),
        pytest.param("some-unknown-table", id="unknown-table"),
    ],
)
def test_load_table_config_returns_none_for_falsy_or_unknown_table_name(table_name, temp_config_env):
    _, manifest_path = temp_config_env

    _write_yaml(manifest_path, {"tables": {}})

    assert load_table_config(table_name) is None


# Verify that None is returned for a table that is disabled in the manifest.
def test_load_table_config_disabled_table_returns_none(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "disabled-table", config_file="tables/disabled-table.yaml", enabled=False)

    assert load_table_config("disabled-table") is None


# Verify that the table's config file is read and parsed correctly.
def test_load_table_config_returns_parsed_config(temp_config_env):
    config_path, manifest_path = temp_config_env

    _write_manifest(manifest_path, "sample-table", config_file="tables/sample-table.yaml")
    _write_yaml(config_path / "tables" / "sample-table.yaml", {
        "table": "sample-table",
        "checks": [],
    })

    config = load_table_config("sample-table")

    assert config is not None
    assert config["table"] == "sample-table"
    assert "checks" in config


# Verify that subsequent calls for the same table return the cached config object.
def test_load_table_config_caches_result(temp_config_env):
    config_path, manifest_path = temp_config_env

    _write_manifest(manifest_path, "sample-table", config_file="tables/sample-table.yaml")
    _write_yaml(config_path / "tables" / "sample-table.yaml", {
        "table": "sample-table",
    })

    first = load_table_config("sample-table")
    second = load_table_config("sample-table")

    assert first is second


# Verify that the manifest is loaded and contains the configured tables.
def test_load_manifest_returns_dict_with_tables(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "sample-table", config_file="tables/sample-table.yaml")

    manifest = load_manifest()

    assert "tables" in manifest
    assert "sample-table" in manifest["tables"]


# Verify that a ValueError is raised when an enabled table has no config path, and
# when the config file's table name doesn't match the requested table.
@pytest.mark.parametrize(
    "table_name,config_file,config_content",
    [
        pytest.param("no-config-table", None, None, id="missing-config-field"),
        pytest.param(
            "table-a",
            "tables/table-a.yaml",
            {"table": "table-b"},
            id="table-mismatch",
        ),
    ],
)
def test_load_table_config_invalid_config_raises_value_error(
    table_name, config_file, config_content, temp_config_env
):
    config_path, manifest_path = temp_config_env

    _write_manifest(manifest_path, table_name, config_file=config_file)

    # config_content is None for the missing-config-field case, which has no config
    # file to write in the first place.
    if config_content is not None:
        _write_yaml(config_path / config_file, config_content)

    with pytest.raises(ValueError):
        load_table_config(table_name)


# Verify that a FileNotFoundError is raised when the table's config file doesn't exist.
def test_load_table_config_missing_file_raises_file_not_found(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "missing-file-table", config_file="tables/does-not-exist.yaml")

    with pytest.raises(FileNotFoundError):
        load_table_config("missing-file-table")


# Verify that a FileNotFoundError is raised when the manifest file doesn't exist.
def test_load_manifest_missing_file_raises_file_not_found(temp_config_env):
    with pytest.raises(FileNotFoundError):
        load_manifest()


# Verify that a ValueError is raised when the manifest is invalid YAML (not a dict).
def test_load_manifest_invalid_yaml_raises_value_error(temp_config_env):
    _, manifest_path = temp_config_env

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_manifest()
