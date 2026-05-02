"""SRE remediation action registry.

Every action the agent is allowed to call is declared here. The LLM tool
definitions are derived from this registry, so the model physically cannot
emit an action outside this set: agent.py validates every tool call against
ALLOWED_ACTIONS before dispatch.

Each entry pairs an admin-api endpoint with:
- preconditions(diagnosis)  — gate the LLM from proposing an obviously wrong action
- risk_class                — informs risk.score(); v1 forces every action to human approval
- params_schema             — JSON-schema-ish dict describing tool call args
- builder(params)           — turns LLM-proposed params into (method, path, body)

`notify` is special-cased because it has no admin-api endpoint.
"""

from typing import Any, Callable, Dict, List, Optional


class ActionSpec:
    def __init__(
        self,
        name: str,
        description: str,
        method: str,
        path_template: Optional[str],
        risk_class: str,
        params_schema: Dict[str, Any],
        builder: Callable[[Dict[str, Any]], Dict[str, Any]],
        preconditions: Callable[[Dict[str, Any]], bool] = lambda _d: True,
    ):
        self.name = name
        self.description = description
        self.method = method
        self.path_template = path_template
        self.risk_class = risk_class
        self.params_schema = params_schema
        self.builder = builder
        self.preconditions = preconditions

    def to_openai_tool(self) -> Dict[str, Any]:
        """Render as an OpenAI tool/function definition for LLM tool-calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.params_schema.get("properties", {}),
                    "required": self.params_schema.get("required", []),
                    "additionalProperties": False,
                },
            },
        }


def _notify_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "notify",
        "summary": params.get("summary", ""),
        "severity": params.get("severity", "info"),
    }


def _failover_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "POST",
        "path": f"/api/v1/sla/failover-rules/{params['failover_rule_id']}/trigger",
        "body": None,
    }


def _failover_precond(diagnosis: Dict[str, Any]) -> bool:
    """Only allow failover when the trigger event identifies a provider/model in distress."""
    payload = diagnosis.get("trigger_payload") or {}
    return bool(payload.get("provider") or payload.get("model"))


def _rate_limit_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    body = {k: v for k, v in params.items() if k != "policy_id"}
    return {
        "kind": "admin_api",
        "method": "PUT",
        "path": f"/api/v1/rate-limits/{params['policy_id']}",
        "body": body,
    }


def _guardrail_warn_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "PUT",
        "path": f"/api/v1/guardrails/{params['guardrail_id']}",
        "body": {"mode": "warn"},
    }


def _cache_clear_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "POST",
        "path": "/api/v1/cache/clear",
        "body": {"team_id": params.get("team_id")} if params.get("team_id") else {},
    }


def _reassign_guardrail_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "POST",
        "path": f"/api/v1/guardrails/{params['guardrail_id']}/assign/{params['team_id']}",
        "body": None,
    }


def _budget_update_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "POST",
        "path": "/api/v1/budgets/update",
        "body": params,
    }


def _deprecate_model_builder(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "admin_api",
        "method": "POST",
        "path": "/api/v1/model-deprecations",
        "body": params,
    }


ALLOWED_ACTIONS: Dict[str, ActionSpec] = {
    "notify": ActionSpec(
        name="notify",
        description=(
            "Send a human-readable summary of the incident to all configured "
            "notification channels (Slack, PagerDuty, email, generic webhook). "
            "Use this for every incident as the first step."
        ),
        method="N/A",
        path_template=None,
        risk_class="auto",
        params_schema={
            "properties": {
                "summary": {"type": "string", "description": "Short incident summary (1-3 sentences)."},
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "description": "Severity for routing.",
                },
            },
            "required": ["summary", "severity"],
        },
        builder=_notify_builder,
    ),
    "trigger_failover": ActionSpec(
        name="trigger_failover",
        description=(
            "Trigger a configured failover rule, switching primary model traffic to its "
            "fallback. Requires a pre-existing failover rule UUID."
        ),
        method="POST",
        path_template="/api/v1/sla/failover-rules/{id}/trigger",
        risk_class="auto",
        params_schema={
            "properties": {
                "failover_rule_id": {
                    "type": "string",
                    "description": "UUID of the provider_failover_rules row to trigger.",
                },
            },
            "required": ["failover_rule_id"],
        },
        builder=_failover_builder,
        preconditions=_failover_precond,
    ),
    "tighten_rate_limit": ActionSpec(
        name="tighten_rate_limit",
        description=(
            "Reduce an existing rate limit policy's RPM/TPM. Use during cost or abuse spikes "
            "to throttle a specific team or key. Reduce by ≤30% per call."
        ),
        method="PUT",
        path_template="/api/v1/rate-limits/{id}",
        risk_class="auto-conditional",
        params_schema={
            "properties": {
                "policy_id": {"type": "string", "description": "UUID of the rate_limit_policies row."},
                "rpm_limit": {"type": "integer", "description": "New requests-per-minute limit."},
                "tpm_limit": {"type": "integer", "description": "New tokens-per-minute limit."},
            },
            "required": ["policy_id"],
        },
        builder=_rate_limit_builder,
    ),
    "tighten_guardrail": ActionSpec(
        name="tighten_guardrail",
        description=(
            "Switch a guardrail to 'warn' mode, escalating logging without blocking. Only "
            "use to move from disabled→warn; switching to 'block' requires human approval."
        ),
        method="PUT",
        path_template="/api/v1/guardrails/{id}",
        risk_class="auto-conditional",
        params_schema={
            "properties": {
                "guardrail_id": {"type": "string", "description": "UUID of the guardrail to update."},
            },
            "required": ["guardrail_id"],
        },
        builder=_guardrail_warn_builder,
    ),
    "clear_cache": ActionSpec(
        name="clear_cache",
        description=(
            "Flush the semantic response cache. Provide team_id to scope to a single team; "
            "omit to clear globally (higher risk)."
        ),
        method="POST",
        path_template="/api/v1/cache/clear",
        risk_class="auto-conditional",
        params_schema={
            "properties": {
                "team_id": {"type": "string", "description": "Team UUID. Omit for global clear."},
            },
            "required": [],
        },
        builder=_cache_clear_builder,
    ),
    "reassign_guardrail": ActionSpec(
        name="reassign_guardrail",
        description="Assign a stricter guardrail config to a team. Always requires human approval.",
        method="POST",
        path_template="/api/v1/guardrails/{id}/assign/{team_id}",
        risk_class="human",
        params_schema={
            "properties": {
                "guardrail_id": {"type": "string", "description": "UUID of the guardrail config."},
                "team_id": {"type": "string", "description": "UUID of the team."},
            },
            "required": ["guardrail_id", "team_id"],
        },
        builder=_reassign_guardrail_builder,
    ),
    "update_budget": ActionSpec(
        name="update_budget",
        description="Cap or freeze a team/key budget on LiteLLM. Always requires human approval.",
        method="POST",
        path_template="/api/v1/budgets/update",
        risk_class="human",
        params_schema={
            "properties": {
                "team_id": {"type": "string"},
                "max_budget": {"type": "number"},
                "soft_budget": {"type": "number"},
            },
            "required": [],
        },
        builder=_budget_update_builder,
    ),
    "deprecate_model": ActionSpec(
        name="deprecate_model",
        description=("Mark a model as deprecated with a sunset date and replacement. Always requires human approval."),
        method="POST",
        path_template="/api/v1/model-deprecations",
        risk_class="human",
        params_schema={
            "properties": {
                "model_name": {"type": "string"},
                "replacement_model": {"type": "string"},
                "sunset_date": {"type": "string", "description": "ISO 8601 date."},
                "reason": {"type": "string"},
            },
            "required": ["model_name"],
        },
        builder=_deprecate_model_builder,
    ),
}


def list_tool_definitions() -> List[Dict[str, Any]]:
    """Return all allowed actions as OpenAI-format tool definitions for LLM tool calling."""
    return [spec.to_openai_tool() for spec in ALLOWED_ACTIONS.values()]


def validate(action: str, params: Dict[str, Any]) -> Optional[str]:
    """Return None if the action+params are well-formed; else an error message."""
    spec = ALLOWED_ACTIONS.get(action)
    if not spec:
        return f"Unknown action: {action!r}"
    required = spec.params_schema.get("required", [])
    for key in required:
        if key not in params:
            return f"Action {action!r} missing required parameter: {key!r}"
    return None
