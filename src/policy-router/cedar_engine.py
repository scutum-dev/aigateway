"""
Cedar Policy Engine wrapper for model routing decisions.

Uses cedarpy to evaluate Cedar policies for intelligent model selection.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

try:
    import cedarpy
    CEDAR_AVAILABLE = True
except ImportError:
    CEDAR_AVAILABLE = False

from models import PolicyEvaluationResponse

logger = logging.getLogger(__name__)


class CedarEngine:
    """
    Cedar policy evaluation engine for routing decisions.

    Evaluates Cedar policies to determine if a model should be selected
    based on cost, latency, budget, and capability constraints.
    """

    def __init__(self, policies_path: str):
        """
        Initialize Cedar engine with policies directory.

        Args:
            policies_path: Path to directory containing .cedar policy files
        """
        self.policies_path = Path(policies_path)
        self.policies: List[str] = []
        self.schema: Optional[str] = None
        self._load_policies()

    def _load_policies(self) -> None:
        """Load all Cedar policies from the configured directory."""
        if not CEDAR_AVAILABLE:
            logger.warning("cedarpy not available, using fallback routing logic")
            return

        if not self.policies_path.exists():
            logger.warning(f"Policies path does not exist: {self.policies_path}")
            return

        self.policies = []

        # Load all .cedar files
        for policy_file in self.policies_path.glob("*.cedar"):
            try:
                content = policy_file.read_text()
                self.policies.append(content)
                logger.info(f"Loaded policy: {policy_file.name}")
            except Exception as e:
                logger.error(f"Failed to load policy {policy_file}: {e}")

        # Load schema if present
        schema_file = self.policies_path / "schema.cedarschema"
        if schema_file.exists():
            try:
                self.schema = schema_file.read_text()
                logger.info("Loaded Cedar schema")
            except Exception as e:
                logger.error(f"Failed to load schema: {e}")

        logger.info(f"Loaded {len(self.policies)} Cedar policies")

    def reload_policies(self) -> int:
        """Reload all policies from disk."""
        self._load_policies()
        return len(self.policies)

    def evaluate(
        self,
        principal: str,
        action: str,
        resource: str,
        context: Dict[str, Any]
    ) -> PolicyEvaluationResponse:
        """
        Evaluate Cedar policies for a given request.

        Args:
            principal: Principal entity (e.g., "user::user-123" or "team::engineering")
            action: Action being performed (e.g., "routing:select_model")
            resource: Resource entity (e.g., "model::gpt-4o")
            context: Context dictionary with budget, latency, metrics

        Returns:
            PolicyEvaluationResponse with decision and reasons
        """
        if not CEDAR_AVAILABLE:
            return PolicyEvaluationResponse(
                decision="allow",
                reasons=["cedarpy not available, defaulting to allow"],
                errors=[]
            )

        if not self.policies:
            return PolicyEvaluationResponse(
                decision="allow",
                reasons=["no policies loaded, defaulting to allow"],
                errors=[]
            )

        try:
            # Build the authorization request
            request = {
                "principal": principal,
                "action": action,
                "resource": resource,
                "context": context
            }

            # Combine all policies
            combined_policies = "\n\n".join(self.policies)

            # Create entities for the request
            entities = self._build_entities(principal, resource, context)

            # Evaluate using cedarpy
            result = cedarpy.is_authorized(
                request=request,
                policies=combined_policies,
                entities=entities,
                schema=self.schema
            )

            decision = "allow" if result.is_allowed else "deny"
            reasons = [str(r) for r in result.reasons] if hasattr(result, 'reasons') else []
            errors = [str(e) for e in result.errors] if hasattr(result, 'errors') else []

            return PolicyEvaluationResponse(
                decision=decision,
                reasons=reasons,
                errors=errors
            )

        except Exception as e:
            logger.error(f"Cedar evaluation error: {e}")
            return PolicyEvaluationResponse(
                decision="allow",
                reasons=[],
                errors=[f"Evaluation error: {str(e)}"]
            )

    def _build_entities(
        self,
        principal: str,
        resource: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build Cedar entities for evaluation."""
        entities = []

        # Parse principal (e.g., "user::user-123")
        if "::" in principal:
            principal_type, principal_id = principal.split("::", 1)
            entities.append({
                "uid": {"type": principal_type, "id": principal_id},
                "attrs": context.get("principal_attrs", {}),
                "parents": []
            })

        # Parse resource (e.g., "model::gpt-4o")
        if "::" in resource:
            resource_type, resource_id = resource.split("::", 1)
            resource_attrs = context.get("resource_attrs", {})

            # Add model-specific attributes
            resource_attrs.update({
                "provider": context.get("provider", "unknown"),
                "average_latency_ms": context.get("current_latency_ms", 1000),
                "current_error_rate": context.get("current_error_rate", 0.0),
                "tier": context.get("tier", "standard")
            })

            entities.append({
                "uid": {"type": resource_type, "id": resource_id},
                "attrs": resource_attrs,
                "parents": []
            })

        return entities

    def evaluate_model_selection(
        self,
        user_id: Optional[str],
        team_id: Optional[str],
        model_id: str,
        model_attrs: Dict[str, Any],
        request_context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Evaluate if a specific model can be selected for a request.

        Args:
            user_id: User making the request
            team_id: Team the user belongs to
            model_id: Model being evaluated
            model_attrs: Model attributes (provider, tier, costs, etc.)
            request_context: Request context (budget, latency SLA, etc.)

        Returns:
            Tuple of (is_allowed, reasons)
        """
        # Build principal
        if user_id:
            principal = f"user::{user_id}"
        elif team_id:
            principal = f"team::{team_id}"
        else:
            principal = "user::anonymous"

        # Build context
        context = {
            **request_context,
            "resource_attrs": model_attrs,
            "provider": model_attrs.get("provider", "unknown"),
            "tier": model_attrs.get("tier", "standard"),
            "current_latency_ms": model_attrs.get("current_latency_ms", 1000),
            "current_error_rate": model_attrs.get("current_error_rate", 0.0),
        }

        # Evaluate
        result = self.evaluate(
            principal=principal,
            action="routing:select_model",
            resource=f"model::{model_id}",
            context=context
        )

        return result.decision == "allow", result.reasons
