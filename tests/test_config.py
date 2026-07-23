"""Tests for the Configuration System (docs/runtime/CONFIGURATION_SYSTEM.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from runtime.config.loader import ConfigLoader
from runtime.config.schema import ConfigLayer
from runtime.errors import ConfigurationError


def test_empty_config_dir_resolves_to_runtime_defaults(config_dir: Path) -> None:
    loader = ConfigLoader(config_dir)
    resolved = loader.resolve()

    assert resolved["log_level"] == "INFO"
    assert resolved.provenance["log_level"] is ConfigLayer.RUNTIME_DEFAULT


def test_missing_config_dir_entirely_is_not_an_error(tmp_path: Path) -> None:
    loader = ConfigLoader(tmp_path / "does_not_exist")
    resolved = loader.resolve()
    assert resolved["log_level"] == "INFO"


def test_global_layer_overrides_runtime_default(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"log_level": "DEBUG"}))
    resolved = ConfigLoader(config_dir).resolve()
    assert resolved["log_level"] == "DEBUG"
    assert resolved.provenance["log_level"] is ConfigLayer.GLOBAL


def test_environment_layer_overrides_global_layer(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"log_level": "DEBUG"}))
    (config_dir / "environments").mkdir()
    (config_dir / "environments" / "production.yaml").write_text(yaml.safe_dump({"log_level": "WARNING"}))

    resolved = ConfigLoader(config_dir, environment="production").resolve()
    assert resolved["log_level"] == "WARNING"
    assert resolved.provenance["log_level"] is ConfigLayer.ENVIRONMENT


def test_module_layer_is_most_specific_among_the_three_tested(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"custom": "global"}))
    (config_dir / "modules").mkdir()
    (config_dir / "modules" / "crawler.yaml").write_text(yaml.safe_dump({"custom": "module"}))

    resolved = ConfigLoader(config_dir).resolve(module_id="crawler")
    assert resolved["custom"] == "module"
    assert resolved.provenance["custom"] is ConfigLayer.MODULE

    # A different, unscoped resolution never sees the module-layer override.
    unscoped = ConfigLoader(config_dir).resolve()
    assert unscoped["custom"] == "global"


def test_a_key_not_set_anywhere_falls_through_to_defaults_without_error(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"unrelated": "value"}))
    resolved = ConfigLoader(config_dir).resolve()
    assert resolved["event_bus_default_queue_size"] == 1000  # untouched Runtime default


def test_malformed_yaml_raises_configuration_error(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text("not: valid: yaml: [unterminated")
    with pytest.raises(ConfigurationError):
        ConfigLoader(config_dir).resolve()


def test_non_mapping_yaml_raises_configuration_error(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump(["a", "list", "not", "a", "mapping"]))
    with pytest.raises(ConfigurationError):
        ConfigLoader(config_dir).resolve()


def test_literal_credential_shaped_value_fails_validation(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"api_key": "sk-literal-secret"}))
    loader = ConfigLoader(config_dir)

    issues = loader.validate()
    assert len(issues) == 1
    assert "api_key" in issues[0].key

    with pytest.raises(ConfigurationError):
        loader.resolve()  # strict=True by default


def test_credential_reference_prefixed_value_passes_validation(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"api_key": "ref:vault://some/secret"}))
    loader = ConfigLoader(config_dir)
    assert loader.validate() == []
    resolved = loader.resolve()
    assert resolved["api_key"] == "ref:vault://some/secret"


def test_non_strict_resolve_does_not_raise_on_invalid_config(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"api_key": "literal-secret"}))
    resolved = ConfigLoader(config_dir).resolve(strict=False)
    assert resolved["api_key"] == "literal-secret"
