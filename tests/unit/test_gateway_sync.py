"""Unit tests for the Admin API gateway_sync module.

Tests the build_gateway_config function that generates Agent Gateway
YAML configuration from MCP server definitions.
"""

import sys
import os
import importlib.util

import pytest
import yaml

# Load the admin-api gateway_sync module under a unique name
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
_service_path = os.path.join(_service_dir, "gateway_sync.py")
sys.path.insert(0, _service_dir)  # needed so yaml import inside gateway_sync.py works
_spec = importlib.util.spec_from_file_location("admin_api_gateway_sync", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_gateway_sync"] = _mod
_spec.loader.exec_module(_mod)

build_gateway_config = _mod.build_gateway_config


# ============================================================================
# build_gateway_config — basic structure
# ============================================================================


class TestBuildGatewayConfigStructure:
    def test_empty_servers_produces_valid_yaml(self):
        """Empty server list should produce valid YAML with empty targets."""
        result = build_gateway_config([])
        parsed = yaml.safe_load(result)
        assert parsed is not None
        targets = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"]
        assert targets == []

    def test_output_is_valid_yaml(self):
        """Output should always be parseable as valid YAML."""
        servers = [
            {"name": "test", "server_type": "stdio", "command": "echo", "url": None, "args": [], "env": {}},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_cors_config_present(self):
        """Output should contain CORS configuration with expected headers."""
        result = build_gateway_config([])
        parsed = yaml.safe_load(result)
        policies = parsed["binds"][0]["listeners"][0]["routes"][0]["policies"]
        cors = policies["cors"]
        assert cors["allowOrigins"] == ["*"]
        assert "content-type" in cors["allowHeaders"]
        assert "mcp-protocol-version" in cors["allowHeaders"]
        assert "Mcp-Session-Id" in cors["exposeHeaders"]


# ============================================================================
# build_gateway_config — stdio servers
# ============================================================================


class TestBuildGatewayConfigStdio:
    def test_single_stdio_server(self):
        """Single stdio server should produce correct cmd and args."""
        servers = [
            {"name": "my-server", "server_type": "stdio", "command": "node", "url": None, "args": ["index.js"], "env": {}},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        targets = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"]
        assert len(targets) == 1
        assert targets[0]["name"] == "my-server"
        assert targets[0]["stdio"]["cmd"] == "node"
        assert targets[0]["stdio"]["args"] == ["index.js"]

    def test_command_with_args_splitting(self):
        """Command with multiple words should split into cmd + extra_args prepended to args."""
        servers = [
            {"name": "npx-server", "server_type": "stdio", "command": "npx -y @modelcontextprotocol/server", "url": None, "args": ["--port", "3001"], "env": {}},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        target = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"][0]
        assert target["stdio"]["cmd"] == "npx"
        assert target["stdio"]["args"] == ["-y", "@modelcontextprotocol/server", "--port", "3001"]

    def test_env_vars_included_when_present(self):
        """Environment variables should be included in stdio config when non-empty."""
        servers = [
            {"name": "env-server", "server_type": "stdio", "command": "python", "url": None, "args": ["serve.py"], "env": {"API_KEY": "secret123", "DEBUG": "true"}},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        target = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"][0]
        assert target["stdio"]["env"]["API_KEY"] == "secret123"
        assert target["stdio"]["env"]["DEBUG"] == "true"

    def test_env_vars_omitted_when_empty(self):
        """Empty env dict should not produce an env key in stdio config."""
        servers = [
            {"name": "no-env", "server_type": "stdio", "command": "python", "url": None, "args": [], "env": {}},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        target = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"][0]
        assert "env" not in target["stdio"]


# ============================================================================
# build_gateway_config — http servers
# ============================================================================


class TestBuildGatewayConfigHttp:
    def test_single_http_server(self):
        """Single http server should produce correct sse/url structure."""
        servers = [
            {"name": "web-server", "server_type": "http", "command": None, "url": "https://api.example.com/mcp", "args": None, "env": None},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        targets = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"]
        assert len(targets) == 1
        assert targets[0]["name"] == "web-server"
        assert targets[0]["sse"]["url"] == "https://api.example.com/mcp"


# ============================================================================
# build_gateway_config — mixed servers
# ============================================================================


class TestBuildGatewayConfigMixed:
    def test_mixed_server_types(self):
        """Mixed stdio and http servers should both appear in targets."""
        servers = [
            {"name": "local-tool", "server_type": "stdio", "command": "python tool.py", "url": None, "args": [], "env": {}},
            {"name": "remote-tool", "server_type": "http", "command": None, "url": "https://remote.example.com/sse", "args": None, "env": None},
        ]
        result = build_gateway_config(servers)
        parsed = yaml.safe_load(result)
        targets = parsed["binds"][0]["listeners"][0]["routes"][0]["backends"][0]["mcp"]["targets"]
        assert len(targets) == 2

        names = {t["name"] for t in targets}
        assert "local-tool" in names
        assert "remote-tool" in names

        stdio_target = next(t for t in targets if t["name"] == "local-tool")
        assert "stdio" in stdio_target
        assert stdio_target["stdio"]["cmd"] == "python"
        assert stdio_target["stdio"]["args"] == ["tool.py"]

        http_target = next(t for t in targets if t["name"] == "remote-tool")
        assert "sse" in http_target
        assert http_target["sse"]["url"] == "https://remote.example.com/sse"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
