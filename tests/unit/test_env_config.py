"""
Tests for environment variable configuration and port consistency.

Validates the .env file, docker-compose port mappings, and cross-service
URL consistency.  No running services or databases required.
"""

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "config" / ".env"
DOCKER_COMPOSE = ROOT / "docker-compose.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_env_file(path: Path) -> list[tuple[str, str, int]]:
    """
    Parse a .env file and return a list of (key, value, line_number) tuples.
    Skips blank lines and comment lines.
    """
    entries: list[tuple[str, str, int]] = []
    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        entries.append((key, value, lineno))
    return entries


def _extract_host_ports(compose: dict) -> dict[str, list[tuple[str, str]]]:
    """
    Return {service_name: [(host_port_str, container_port_str), ...]}.
    Resolves ${VAR:-default} to the default value.
    """
    port_re = re.compile(
        r"""
        (?:"\s*)?                # optional leading quote
        (?:\$\{[A-Z_]+:-)?      # optional ${VAR:-  prefix
        (\d+)                    # host port
        \}?                      # optional closing }
        :(\d+)                   # :container_port
        """,
        re.VERBOSE,
    )
    result: dict[str, list[tuple[str, str]]] = {}
    for name, svc in compose.get("services", {}).items():
        ports = svc.get("ports", [])
        pairs = []
        for entry in ports:
            match = port_re.search(str(entry))
            if match:
                pairs.append((match.group(1), match.group(2)))
        if pairs:
            result[name] = pairs
    return result


# ===========================================================================
# .env File Tests
# ===========================================================================

class TestEnvFile:
    """Validate config/.env structure and content."""

    def test_env_file_exists(self):
        assert ENV_FILE.exists(), f".env file not found at {ENV_FILE}"

    @pytest.fixture(autouse=True)
    def load_env(self):
        if not ENV_FILE.exists():
            pytest.skip(".env file not found")
        self.entries = _parse_env_file(ENV_FILE)
        self.env_dict = {k: v for k, v, _ in self.entries}

    def test_contains_litellm_master_key(self):
        """LITELLM_MASTER_KEY must be defined."""
        assert "LITELLM_MASTER_KEY" in self.env_dict, (
            "LITELLM_MASTER_KEY not found in .env"
        )

    def test_contains_postgres_user(self):
        assert "POSTGRES_USER" in self.env_dict

    def test_contains_postgres_password(self):
        assert "POSTGRES_PASSWORD" in self.env_dict

    def test_contains_postgres_db(self):
        assert "POSTGRES_DB" in self.env_dict

    def test_contains_jwt_secret(self):
        assert "JWT_SECRET" in self.env_dict or "JWT_SECRET_KEY" in self.env_dict, (
            "Neither JWT_SECRET nor JWT_SECRET_KEY found in .env"
        )

    def test_no_duplicate_variable_names(self):
        """Variable names should not be repeated in the .env file."""
        keys = [k for k, _, _ in self.entries]
        duplicates = [k for k, count in __import__("collections").Counter(keys).items() if count > 1]
        assert duplicates == [], f"Duplicate variable names: {duplicates}"

    def test_no_empty_critical_variables(self):
        """Critical variables must have non-empty values."""
        critical = [
            "LITELLM_MASTER_KEY",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        ]
        for key in critical:
            if key in self.env_dict:
                assert self.env_dict[key] != "", f"{key} is empty in .env"

    def test_litellm_master_key_is_not_placeholder(self):
        """LITELLM_MASTER_KEY should not be a bare placeholder like 'changeme'."""
        val = self.env_dict.get("LITELLM_MASTER_KEY", "")
        assert val.lower() not in ("changeme", "change-me", ""), (
            "LITELLM_MASTER_KEY looks like a placeholder"
        )

    def test_port_values_are_numeric(self):
        """Any variable ending in _PORT should have a numeric value."""
        for key, value, lineno in self.entries:
            if key.endswith("_PORT"):
                assert value.isdigit(), (
                    f"{key}={value} (line {lineno}) is not a numeric port"
                )


# ===========================================================================
# Port Assignment Tests
# ===========================================================================

class TestPortAssignments:
    """Validate port mappings extracted from docker-compose.yaml."""

    @pytest.fixture(autouse=True)
    def load_compose(self):
        assert DOCKER_COMPOSE.exists()
        with open(DOCKER_COMPOSE) as f:
            self.compose = yaml.safe_load(f)
        self.port_map = _extract_host_ports(self.compose)

    def test_no_host_port_conflicts_in_default_services(self):
        """Default-profile services must not share host ports."""
        seen: dict[str, str] = {}
        for svc_name, pairs in self.port_map.items():
            profiles = self.compose["services"][svc_name].get("profiles", [])
            if profiles:
                continue  # skip non-default-profile services
            for host_port, _ in pairs:
                if host_port in seen:
                    pytest.fail(
                        f"Host port {host_port} conflict between "
                        f"'{seen[host_port]}' and '{svc_name}'"
                    )
                seen[host_port] = svc_name

    def test_litellm_default_port_is_4000(self):
        """LiteLLM should be mapped to host port 4000 by default."""
        pairs = self.port_map.get("litellm", [])
        host_ports = [hp for hp, _ in pairs]
        assert "4000" in host_ports, f"LiteLLM host ports: {host_ports}"

    def test_admin_api_default_port_is_8086(self):
        pairs = self.port_map.get("admin-api", [])
        host_ports = [hp for hp, _ in pairs]
        assert "8086" in host_ports, f"admin-api host ports: {host_ports}"

    def test_admin_ui_default_port_is_5173(self):
        pairs = self.port_map.get("admin-ui", [])
        host_ports = [hp for hp, _ in pairs]
        assert "5173" in host_ports, f"admin-ui host ports: {host_ports}"

    def test_postgres_default_port_is_5432(self):
        pairs = self.port_map.get("postgres", [])
        host_ports = [hp for hp, _ in pairs]
        assert "5432" in host_ports, f"postgres host ports: {host_ports}"

    def test_redis_default_port_is_6379(self):
        pairs = self.port_map.get("redis", [])
        host_ports = [hp for hp, _ in pairs]
        assert "6379" in host_ports, f"redis host ports: {host_ports}"

    def test_grafana_default_port_is_3030(self):
        pairs = self.port_map.get("grafana", [])
        host_ports = [hp for hp, _ in pairs]
        assert "3030" in host_ports, f"grafana host ports: {host_ports}"

    def test_prometheus_default_port_is_9090(self):
        pairs = self.port_map.get("prometheus", [])
        host_ports = [hp for hp, _ in pairs]
        assert "9090" in host_ports, f"prometheus host ports: {host_ports}"

    def test_landing_ui_default_port_is_9999(self):
        pairs = self.port_map.get("landing-ui", [])
        host_ports = [hp for hp, _ in pairs]
        assert "9999" in host_ports, f"landing-ui host ports: {host_ports}"


# ===========================================================================
# Service URL Consistency Tests
# ===========================================================================

class TestServiceURLConsistency:
    """Cross-check URLs in .env against docker-compose port mappings."""

    @pytest.fixture(autouse=True)
    def load_data(self):
        if not ENV_FILE.exists():
            pytest.skip(".env not found")
        self.env_dict = {k: v for k, v, _ in _parse_env_file(ENV_FILE)}
        with open(DOCKER_COMPOSE) as f:
            self.compose = yaml.safe_load(f)
        self.port_map = _extract_host_ports(self.compose)

    def test_litellm_port_matches_env(self):
        """LITELLM_PORT in .env should match the default host port in compose."""
        env_port = self.env_dict.get("LITELLM_PORT", "4000")
        compose_ports = [hp for hp, _ in self.port_map.get("litellm", [])]
        assert env_port in compose_ports, (
            f"LITELLM_PORT={env_port} not in compose ports {compose_ports}"
        )

    def test_admin_api_port_matches_env(self):
        env_port = self.env_dict.get("ADMIN_API_PORT", "8086")
        compose_ports = [hp for hp, _ in self.port_map.get("admin-api", [])]
        assert env_port in compose_ports, (
            f"ADMIN_API_PORT={env_port} not in compose ports {compose_ports}"
        )

    def test_admin_ui_port_matches_env(self):
        env_port = self.env_dict.get("ADMIN_UI_PORT", "5173")
        compose_ports = [hp for hp, _ in self.port_map.get("admin-ui", [])]
        assert env_port in compose_ports, (
            f"ADMIN_UI_PORT={env_port} not in compose ports {compose_ports}"
        )

    def test_litellm_url_in_admin_api_env(self):
        """admin-api service should reference litellm on the correct internal port."""
        admin_api = self.compose["services"].get("admin-api", {})
        env_vars = admin_api.get("environment", {})
        litellm_url = env_vars.get("LITELLM_URL", "")
        # The internal URL should point to litellm container on port 4000
        assert "litellm" in litellm_url and "4000" in litellm_url, (
            f"admin-api LITELLM_URL does not reference litellm:4000: {litellm_url}"
        )
