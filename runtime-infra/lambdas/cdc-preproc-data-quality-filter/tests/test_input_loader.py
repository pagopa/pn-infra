import pytest
import yaml

import processor.input_loader as input_loader
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


@pytest.fixture
def temp_config_env(tmp_path, monkeypatch):
    config_path = tmp_path / "config"
    manifest_path = config_path / "manifest.yaml"

    monkeypatch.setattr(input_loader, "CONFIG_PATH", config_path)
    monkeypatch.setattr(input_loader, "MANIFEST_PATH", manifest_path)

    return config_path, manifest_path


# test che verifica che venga restituito None quando il nome tabella è vuoto o assente
def test_load_table_config_returns_none_for_falsy_table_name():
    assert load_table_config(None) is None
    assert load_table_config("") is None


# test che verifica che venga restituito None per una tabella non presente nel manifest
def test_load_table_config_returns_none_for_unknown_table(temp_config_env):
    _, manifest_path = temp_config_env

    _write_yaml(manifest_path, {"tables": {}})

    assert load_table_config("some-unknown-table") is None


# test che verifica che la configurazione della tabella venga letta e restituita correttamente
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


# test che verifica che chiamate successive per la stessa tabella restituiscano l'oggetto di configurazione dalla cache
def test_load_table_config_caches_result(temp_config_env):
    config_path, manifest_path = temp_config_env

    _write_manifest(manifest_path, "sample-table", config_file="tables/sample-table.yaml")
    _write_yaml(config_path / "tables" / "sample-table.yaml", {
        "table": "sample-table",
    })

    first = load_table_config("sample-table")
    second = load_table_config("sample-table")

    assert first is second


# test che verifica che il manifest venga letto e contenga le tabelle configurate
def test_load_manifest_returns_dict_with_tables(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "sample-table", config_file="tables/sample-table.yaml")

    manifest = load_manifest()

    assert "tables" in manifest
    assert "sample-table" in manifest["tables"]


# test che verifica che venga restituito None per una tabella disabilitata nel manifest
def test_load_table_config_disabled_table_returns_none(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "disabled-table", config_file="tables/disabled-table.yaml", enabled=False)

    assert load_table_config("disabled-table") is None


# test che verifica che venga sollevato un errore se manca il percorso di configurazione per una tabella abilitata
def test_load_table_config_missing_config_field_raises_value_error(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "no-config-table")

    with pytest.raises(ValueError):
        load_table_config("no-config-table")


# test che verifica che venga sollevato un errore se il nome tabella nel file di configurazione non corrisponde a quello atteso
def test_load_table_config_table_mismatch_raises_value_error(temp_config_env):
    config_path, manifest_path = temp_config_env

    _write_manifest(manifest_path, "table-a", config_file="tables/table-a.yaml")
    _write_yaml(config_path / "tables" / "table-a.yaml", {
        "table": "table-b",
    })

    with pytest.raises(ValueError):
        load_table_config("table-a")


# test che verifica che venga sollevato un errore quando il file di configurazione della tabella non esiste
def test_load_table_config_missing_file_raises_file_not_found(temp_config_env):
    _, manifest_path = temp_config_env

    _write_manifest(manifest_path, "missing-file-table", config_file="tables/does-not-exist.yaml")

    with pytest.raises(FileNotFoundError):
        load_table_config("missing-file-table")


# test che verifica che venga sollevato un errore quando il file manifest non esiste
def test_load_manifest_missing_file_raises_file_not_found(temp_config_env):
    with pytest.raises(FileNotFoundError):
        load_manifest()


# test che verifica che venga sollevato un errore quando il manifest contiene uno YAML non valido (non un dizionario)
def test_load_manifest_invalid_yaml_raises_value_error(temp_config_env):
    _, manifest_path = temp_config_env

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_manifest()
