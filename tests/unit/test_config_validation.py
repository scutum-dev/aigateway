"""
Tests for configuration file validation.

Validates that all configuration files (LiteLLM, Docker Compose, feature flags,
Cedar policies) are syntactically correct and contain expected structure.
No running services or databases required.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
LITELLM_CONFIG = ROOT / "config" / "litellm" / "config.yaml"
DOCKER_COMPOSE = ROOT / "docker-compose.yaml"
FEATURE_FLAGS_DIR = ROOT / "config" / "feature-flags"
CEDAR_POLICIES_DIR = ROOT / "config" / "agentgateway" / "policies"


# ===========================================================================
# LiteLLM Config Tests
# ===========================================================================

class TestLiteLLMConfig:
    """Validate config/litellm/config.yaml structure and content."""

    @pytest.fixture(autouse=True)
    def load_config(self):
        assert LITELLM_CONFIG.exists(), f"LiteLLM config not found: {LITELLM_CONFIG}"
        with open(LITELLM_CONFIG) as f:
            self.config = yaml.safe_load(f)

    def test_valid_yaml_loads_without_error(self):
        """The YAML file must parse without raising an exception."""
        assert self.config is not None

    def test_has_model_list_key(self):
        """Top-level key 'model_list' must be present."""
        assert "model_list" in self.config, "Missing 'model_list' key"

    def test_model_list_is_a_list(self):
        """model_list must be a list."""
        assert isinstance(self.config["model_list"], list)

    def test_every_model_has_model_name(self):
        """Each model entry must have a 'model_name' string."""
        for idx, entry in enumerate(self.config["model_list"]):
            assert "model_name" in entry, f"model_list[{idx}] missing 'model_name'"
            assert isinstance(entry["model_name"], str), (
                f"model_list[{idx}].model_name is not a string"
            )

    def test_every_model_has_litellm_params_with_model(self):
        """Each model entry must have 'litellm_params' containing a 'model' key."""
        for idx, entry in enumerate(self.config["model_list"]):
            assert "litellm_params" in entry, (
                f"model_list[{idx}] missing 'litellm_params'"
            )
            params = entry["litellm_params"]
            assert "model" in params, (
                f"model_list[{idx}].litellm_params missing 'model' key"
            )

    def test_no_duplicate_model_names(self):
        """model_name values must be unique across the entire model_list."""
        names = [e["model_name"] for e in self.config["model_list"]]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        assert duplicates == [], f"Duplicate model_name values: {duplicates}"

    def test_model_count_at_least_50(self):
        """Sanity check: the platform should define >= 50 models."""
        count = len(self.config["model_list"])
        assert count >= 50, f"Expected >= 50 models, found {count}"

    def test_litellm_params_model_is_string(self):
        """litellm_params.model must be a non-empty string."""
        for idx, entry in enumerate(self.config["model_list"]):
            model_val = entry.get("litellm_params", {}).get("model")
            assert isinstance(model_val, str) and len(model_val) > 0, (
                f"model_list[{idx}].litellm_params.model is not a non-empty string"
            )

    def test_known_providers_represented(self):
        """At least the major providers should appear in model names or params."""
        all_models_str = yaml.dump(self.config["model_list"]).lower()
        for provider in ["openai", "anthropic", "gemini", "bedrock"]:
            assert provider in all_models_str or provider.replace("-", "") in all_models_str, (
                f"Provider '{provider}' not found in model list"
            )

    def test_timeout_values_are_positive_integers(self):
        """When a timeout is specified, it must be a positive number."""
        for idx, entry in enumerate(self.config["model_list"]):
            timeout = entry.get("litellm_params", {}).get("timeout")
            if timeout is not None:
                assert isinstance(timeout, (int, float)) and timeout > 0, (
                    f"model_list[{idx}] has non-positive timeout: {timeout}"
                )


# ===========================================================================
# Docker Compose Tests
# ===========================================================================

class TestDockerCompose:
    """Validate docker-compose.yaml structure."""

    @pytest.fixture(autouse=True)
    def load_compose(self):
        assert DOCKER_COMPOSE.exists(), f"Docker compose not found: {DOCKER_COMPOSE}"
        with open(DOCKER_COMPOSE) as f:
            self.compose = yaml.safe_load(f)

    def test_valid_yaml(self):
        """docker-compose.yaml must parse without error."""
        assert self.compose is not None

    def test_has_services_key(self):
        """Top-level 'services' key must be present."""
        assert "services" in self.compose

    def test_all_services_have_image_or_build(self):
        """Every service must have either 'image' or 'build' defined."""
        for name, svc in self.compose["services"].items():
            has_image = "image" in svc
            has_build = "build" in svc
            assert has_image or has_build, (
                f"Service '{name}' has neither 'image' nor 'build'"
            )

    @pytest.mark.parametrize("service_name", [
        "postgres", "redis", "litellm", "admin-api", "admin-ui",
    ])
    def test_required_service_exists(self, service_name):
        """Core services must be defined in docker-compose."""
        assert service_name in self.compose["services"], (
            f"Required service '{service_name}' not found"
        )

    def test_no_duplicate_host_port_mappings(self):
        """No two services should map the same host port."""
        host_ports: dict[str, str] = {}
        port_re = re.compile(
            r"""
            (?:\$\{[A-Z_]+:-)?    # optional ${VAR:-  prefix
            (\d+)                  # host port (capture group 1)
            \}?                    # optional closing }
            :\d+                   # :container_port
            """,
            re.VERBOSE,
        )
        for name, svc in self.compose["services"].items():
            ports = svc.get("ports", [])
            for port_entry in ports:
                port_str = str(port_entry)
                match = port_re.search(port_str)
                if match:
                    host_port = match.group(1)
                    if host_port in host_ports:
                        # Only flag if both services are in the default profile (no profiles key)
                        other = host_ports[host_port]
                        other_profiles = self.compose["services"][other].get("profiles", [])
                        current_profiles = svc.get("profiles", [])
                        # Both have no profile = true conflict
                        if not other_profiles and not current_profiles:
                            pytest.fail(
                                f"Host port {host_port} is used by both "
                                f"'{other}' and '{name}'"
                            )
                    host_ports[host_port] = name

    def test_services_have_valid_restart_policy(self):
        """Services should use a known restart policy."""
        valid_policies = {"no", "always", "unless-stopped", "on-failure"}
        for name, svc in self.compose["services"].items():
            restart = svc.get("restart")
            if restart is not None:
                assert restart in valid_policies, (
                    f"Service '{name}' has unknown restart policy: {restart}"
                )

    def test_networks_key_exists(self):
        """Top-level 'networks' key must be defined."""
        assert "networks" in self.compose

    def test_volumes_key_exists(self):
        """Top-level 'volumes' key must be defined."""
        assert "volumes" in self.compose

    def test_postgres_uses_alpine_image(self):
        """Postgres service should use the alpine variant."""
        pg = self.compose["services"]["postgres"]
        image = pg.get("image", "")
        assert "alpine" in image, f"Postgres image is not alpine: {image}"

    def test_redis_uses_alpine_image(self):
        """Redis service should use the alpine variant."""
        redis_svc = self.compose["services"]["redis"]
        image = redis_svc.get("image", "")
        assert "alpine" in image, f"Redis image is not alpine: {image}"


# ===========================================================================
# Feature Flags Tests
# ===========================================================================

class TestFeatureFlags:
    """Validate feature flag YAML files."""

    def test_feature_flags_directory_exists(self):
        assert FEATURE_FLAGS_DIR.is_dir(), (
            f"Feature flags directory not found: {FEATURE_FLAGS_DIR}"
        )

    def test_base_yaml_exists(self):
        base = FEATURE_FLAGS_DIR / "base.yaml"
        assert base.exists(), "base.yaml not found in feature-flags directory"

    def test_all_yaml_files_are_valid(self):
        """Every .yaml file in the feature-flags dir must parse without error."""
        yaml_files = list(FEATURE_FLAGS_DIR.glob("*.yaml"))
        assert len(yaml_files) > 0, "No YAML files in feature-flags directory"
        for path in yaml_files:
            with open(path) as f:
                data = yaml.safe_load(f)
            assert data is not None, f"{path.name} parsed to None (empty file?)"

    def test_base_yaml_has_features_key(self):
        """base.yaml should define a 'features' section."""
        with open(FEATURE_FLAGS_DIR / "base.yaml") as f:
            data = yaml.safe_load(f)
        assert "features" in data, "base.yaml is missing 'features' key"

    def test_base_yaml_has_version(self):
        """base.yaml should declare a version field."""
        with open(FEATURE_FLAGS_DIR / "base.yaml") as f:
            data = yaml.safe_load(f)
        assert "version" in data, "base.yaml is missing 'version' key"

    def test_environment_files_present(self):
        """dev, staging, and production configs should exist."""
        for env in ["dev.yaml", "staging.yaml", "production.yaml"]:
            path = FEATURE_FLAGS_DIR / env
            assert path.exists(), f"Feature flag file missing: {env}"


# ===========================================================================
# Cedar Policies Tests
# ===========================================================================

class TestCedarPolicies:
    """Validate Cedar policy files if present."""

    @pytest.fixture(autouse=True)
    def check_dir(self):
        if not CEDAR_POLICIES_DIR.is_dir():
            pytest.skip("Cedar policies directory not found; skipping")

    def test_policy_files_exist(self):
        """At least one .cedar file should exist."""
        cedar_files = list(CEDAR_POLICIES_DIR.glob("*.cedar"))
        assert len(cedar_files) > 0, "No .cedar files found"

    def test_rbac_policy_exists(self):
        """An RBAC policy file should be present."""
        rbac = CEDAR_POLICIES_DIR / "rbac.cedar"
        assert rbac.exists(), "rbac.cedar not found"

    def test_entity_file_exists(self):
        """An entity definitions file should be present."""
        entities = CEDAR_POLICIES_DIR / "entities.cedar"
        assert entities.exists(), "entities.cedar not found"

    def test_entity_json_files_are_valid(self):
        """Any .json files in the policy directory must be valid JSON."""
        json_files = list(CEDAR_POLICIES_DIR.glob("*.json"))
        for path in json_files:
            with open(path) as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"{path.name} is not valid JSON: {e}")

    def test_cedar_files_are_non_empty(self):
        """Cedar policy files should not be empty."""
        for path in CEDAR_POLICIES_DIR.glob("*.cedar"):
            content = path.read_text().strip()
            assert len(content) > 0, f"{path.name} is empty"
