"""
Gateway Sync Module

Syncs MCP server configurations from the admin database to the
Agent Gateway's Kubernetes ConfigMap, then triggers a rolling restart.
"""

import os
import logging
from datetime import datetime, timezone

import httpx
import yaml

logger = logging.getLogger(__name__)

# K8s in-cluster API config
K8S_API = "https://kubernetes.default.svc"
SA_NS_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def _k8s_namespace() -> str:
    """Detect namespace from in-cluster serviceaccount, with env var override."""
    ns = os.getenv("K8S_NAMESPACE")
    if ns:
        return ns
    try:
        with open(SA_NS_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "default"
CONFIGMAP_NAME = os.getenv("GATEWAY_CONFIGMAP_NAME", "agentgateway-config")
DEPLOYMENT_NAME = os.getenv("GATEWAY_DEPLOYMENT_NAME", "agentgateway")
SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def _k8s_headers() -> dict:
    """Read the in-cluster service account token and return auth headers."""
    with open(SA_TOKEN_PATH) as f:
        token = f.read().strip()
    return {"Authorization": f"Bearer {token}"}


def _in_cluster() -> bool:
    """Return True when running inside a Kubernetes pod."""
    return os.path.exists(SA_TOKEN_PATH)


def build_gateway_config(servers: list[dict]) -> str:
    """Generate agentgateway config.yaml from a list of active MCP servers.

    Each server dict must have: name, server_type, command, url, args, env.
    Maps stdio → {name, stdio: {cmd, args, env}}, http → {name, sse: {url}}.
    """
    targets = []
    for s in servers:
        if s["server_type"] == "stdio":
            # Build the command + args list
            # The first token of `command` is cmd, rest are prepended to args
            parts = (s.get("command") or "").split()
            cmd = parts[0] if parts else ""
            extra_args = parts[1:] if len(parts) > 1 else []
            args = extra_args + (s.get("args") or [])

            target: dict = {"name": s["name"], "stdio": {"cmd": cmd, "args": args}}

            # Include env vars if present
            env = s.get("env") or {}
            if env:
                target["stdio"]["env"] = env

            targets.append(target)
        elif s["server_type"] == "http":
            targets.append({"name": s["name"], "sse": {"url": s.get("url") or ""}})

    config = {
        "binds": [{
            "port": 3000,
            "listeners": [{
                "routes": [{
                    "policies": {
                        "cors": {
                            "allowOrigins": ["*"],
                            "allowHeaders": [
                                "mcp-protocol-version",
                                "content-type",
                                "authorization",
                                "accept",
                            ],
                            "exposeHeaders": ["Mcp-Session-Id"],
                        }
                    },
                    "backends": [{
                        "mcp": {"targets": targets}
                    }],
                }]
            }]
        }]
    }

    return yaml.dump(config, default_flow_style=False, sort_keys=False)


async def sync_configmap(servers: list[dict]) -> dict:
    """PATCH the agentgateway ConfigMap with generated config.

    Returns {"status": "ok"} on success or {"status": "error", "message": ...}.
    """
    if not _in_cluster():
        return {"status": "error", "message": "Not running in Kubernetes — sync unavailable in local dev"}

    config_yaml = build_gateway_config(servers)

    patch_body = {
        "data": {
            "config.yaml": config_yaml,
        }
    }

    ns = _k8s_namespace()
    url = f"{K8S_API}/api/v1/namespaces/{ns}/configmaps/{CONFIGMAP_NAME}"
    headers = _k8s_headers()
    headers["Content-Type"] = "application/strategic-merge-patch+json"

    async with httpx.AsyncClient(verify=SA_CA_PATH) as client:
        resp = await client.patch(url, json=patch_body, headers=headers, timeout=10.0)

    if resp.status_code in (200, 201):
        return {"status": "ok"}

    return {"status": "error", "message": f"K8s API {resp.status_code}: {resp.text[:500]}"}


async def restart_gateway() -> dict:
    """Patch the agentgateway Deployment annotation to trigger a rolling restart.

    Returns {"status": "ok"} on success or {"status": "error", "message": ...}.
    """
    if not _in_cluster():
        return {"status": "error", "message": "Not running in Kubernetes — restart unavailable in local dev"}

    now = datetime.now(timezone.utc).isoformat()
    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "admin-api/restartedAt": now,
                    }
                }
            }
        }
    }

    ns = _k8s_namespace()
    url = (
        f"{K8S_API}/apis/apps/v1/namespaces/{ns}"
        f"/deployments/{DEPLOYMENT_NAME}"
    )
    headers = _k8s_headers()
    headers["Content-Type"] = "application/strategic-merge-patch+json"

    async with httpx.AsyncClient(verify=SA_CA_PATH) as client:
        resp = await client.patch(url, json=patch_body, headers=headers, timeout=10.0)

    if resp.status_code in (200, 201):
        return {"status": "ok"}

    return {"status": "error", "message": f"K8s API {resp.status_code}: {resp.text[:500]}"}
