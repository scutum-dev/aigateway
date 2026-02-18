"""
Gateway Sync Module

Syncs MCP server configurations from the admin database to the
Agent Gateway config file.

- Local dev (Docker Compose): writes config.yaml to a shared volume;
  agentgateway's file watcher hot-reloads automatically.
- Kubernetes: patches ConfigMap + triggers rolling restart.
"""

import logging
import os
from datetime import datetime, timezone

import httpx
import yaml

logger = logging.getLogger(__name__)

# Shared-volume path (set via GATEWAY_CONFIG_PATH env)
GATEWAY_CONFIG_PATH = os.getenv("GATEWAY_CONFIG_PATH", "")

# K8s in-cluster API config
K8S_API = "https://kubernetes.default.svc"
SA_NS_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
CONFIGMAP_NAME = os.getenv("GATEWAY_CONFIGMAP_NAME", "agentgateway-config")
DEPLOYMENT_NAME = os.getenv("GATEWAY_DEPLOYMENT_NAME", "agentgateway")


def _k8s_namespace() -> str:
    ns = os.getenv("K8S_NAMESPACE")
    if ns:
        return ns
    try:
        with open(SA_NS_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "default"


def _k8s_headers() -> dict:
    with open(SA_TOKEN_PATH) as f:
        token = f.read().strip()
    return {"Authorization": f"Bearer {token}"}


def _in_cluster() -> bool:
    return os.path.exists(SA_TOKEN_PATH)


def build_gateway_config(servers: list[dict], agents: list[dict] | None = None) -> str:
    """Generate agentgateway config.yaml from active MCP servers and A2A agents."""
    mcp_targets = []
    for s in servers:
        if s["server_type"] == "stdio":
            parts = (s.get("command") or "").split()
            cmd = parts[0] if parts else ""
            extra_args = parts[1:] if len(parts) > 1 else []
            args = extra_args + (s.get("args") or [])

            target: dict = {"name": s["name"], "stdio": {"cmd": cmd, "args": args}}

            env = s.get("env") or {}
            if env:
                target["stdio"]["env"] = env

            mcp_targets.append(target)
        elif s["server_type"] == "http":
            mcp_targets.append({"name": s["name"], "sse": {"url": s.get("url") or ""}})

    backends: list[dict] = [{"mcp": {"targets": mcp_targets}}]

    # Add A2A backend if agents are provided
    if agents:
        a2a_targets = [{"name": a["name"], "url": a["url"]} for a in agents]
        backends.append({"a2a": {"targets": a2a_targets}})

    config = {
        "binds": [
            {
                "port": 3000,
                "listeners": [
                    {
                        "routes": [
                            {
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
                                "backends": backends,
                            }
                        ]
                    }
                ],
            }
        ]
    }

    return yaml.dump(config, default_flow_style=False, sort_keys=False)


async def sync_configmap(servers: list[dict], agents: list[dict] | None = None) -> dict:
    """Deploy active MCP server and A2A agent configs to the Agent Gateway.

    - Docker Compose: writes config.yaml to a shared volume (hot-reload).
    - Kubernetes: PATCHes the ConfigMap.
    """
    config_yaml = build_gateway_config(servers, agents)

    # Docker Compose path — write to shared volume
    if GATEWAY_CONFIG_PATH:
        try:
            os.makedirs(os.path.dirname(GATEWAY_CONFIG_PATH), exist_ok=True)
            with open(GATEWAY_CONFIG_PATH, "w") as f:
                f.write(config_yaml)
            logger.info("Wrote gateway config to %s (%d servers)", GATEWAY_CONFIG_PATH, len(servers))
            return {"status": "ok", "method": "file"}
        except OSError as exc:
            return {"status": "error", "message": f"Failed to write config: {exc}"}

    # Kubernetes path — patch ConfigMap
    if _in_cluster():
        patch_body = {"data": {"config.yaml": config_yaml}}
        ns = _k8s_namespace()
        url = f"{K8S_API}/api/v1/namespaces/{ns}/configmaps/{CONFIGMAP_NAME}"
        headers = _k8s_headers()
        headers["Content-Type"] = "application/strategic-merge-patch+json"

        async with httpx.AsyncClient(verify=SA_CA_PATH) as client:
            resp = await client.patch(url, json=patch_body, headers=headers, timeout=10.0)

        if resp.status_code in (200, 201):
            return {"status": "ok", "method": "configmap"}
        return {"status": "error", "message": f"K8s API {resp.status_code}: {resp.text[:500]}"}

    return {"status": "error", "message": "No sync target: set GATEWAY_CONFIG_PATH or run in Kubernetes"}


async def restart_gateway() -> dict:
    """Trigger a gateway restart (Kubernetes only; Docker Compose uses file watcher)."""
    if GATEWAY_CONFIG_PATH:
        # Docker Compose: agentgateway watches config.yaml, no restart needed
        return {"status": "ok", "method": "file-watch"}

    if not _in_cluster():
        return {"status": "ok", "method": "skipped"}

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
    url = f"{K8S_API}/apis/apps/v1/namespaces/{ns}/deployments/{DEPLOYMENT_NAME}"
    headers = _k8s_headers()
    headers["Content-Type"] = "application/strategic-merge-patch+json"

    async with httpx.AsyncClient(verify=SA_CA_PATH) as client:
        resp = await client.patch(url, json=patch_body, headers=headers, timeout=10.0)

    if resp.status_code in (200, 201):
        return {"status": "ok", "method": "rolling-restart"}

    return {"status": "error", "message": f"K8s API {resp.status_code}: {resp.text[:500]}"}
