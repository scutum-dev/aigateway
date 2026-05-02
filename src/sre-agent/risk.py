"""Risk scoring for proposed remediation actions.

Pure functions, table-driven so unit tests can exercise every cell. v1
behavior: even when score < threshold, the decision is forced to 'human'
because SRE_AUTO_APPROVE defaults false. The score is still computed and
recorded for v2.
"""

import os
from typing import Any, Dict, Tuple

from actions import ALLOWED_ACTIONS

# Base risk per action.
BASE_SCORE: Dict[str, int] = {
    "notify": 0,
    "trigger_failover": 10,
    "clear_cache": 15,
    "tighten_rate_limit": 30,
    "tighten_guardrail": 30,
    "reassign_guardrail": 70,
    "update_budget": 90,
    "deprecate_model": 95,
}


def score(
    action: str,
    params: Dict[str, Any],
    diagnosis: Dict[str, Any],
) -> Tuple[int, str]:
    """Return (score 0-100, decision 'auto'|'human').

    v1 always returns 'human' regardless of score; we compute the score so the
    UI and audit log capture what the policy WOULD have done.
    """
    base = BASE_SCORE.get(action, 100)
    modifiers = 0

    # Org-wide scope amplifies blast radius. Only fire when the action explicitly
    # targets all teams ('*') or scope='org' — absent team_id is not org-wide.
    if params.get("scope") == "org" or params.get("team_id") == "*":
        if action in ("tighten_rate_limit", "clear_cache", "tighten_guardrail"):
            modifiers += 10

    # Population at risk.
    affected = diagnosis.get("affected_users") or 0
    if affected > 100:
        modifiers += 15

    # Oscillation guard: if recent audit shows this same action applied and
    # reverted in the last 24h, raise the score to force human review.
    recent_changes = diagnosis.get("recent_audit_for_resource") or []
    if any(c.get("action") == "revert" for c in recent_changes):
        modifiers += 20

    raw = max(0, min(100, base + modifiers))

    spec = ALLOWED_ACTIONS.get(action)
    if spec and spec.risk_class == "human":
        return raw, "human"

    threshold = int(os.getenv("SRE_RISK_THRESHOLD", "40"))
    auto_approve = os.getenv("SRE_AUTO_APPROVE", "false").lower() == "true"

    if not auto_approve:
        return raw, "human"
    if raw < threshold:
        return raw, "auto"
    return raw, "human"
