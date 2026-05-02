"""LLM-driven remediation proposer.

Uses an OpenAI-compatible client pointed at LiteLLM (the local proxy at port
4000). Tool calling is constrained to actions.ALLOWED_ACTIONS — the LLM
cannot emit any other tool name. The system prompt is structured for prompt
caching (long static instructions, then the per-incident diagnosis).
"""

import json
import logging
import os
from typing import Any, Dict, List

import actions
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an SRE agent for an AI gateway platform. You receive an incident \
diagnosis (metrics, recent events, audit trail, available failover rules) and propose a \
remediation plan as a sequence of tool calls.

Hard rules:
- You may ONLY call tools from the provided list. Calls to other names are rejected.
- Always include a `notify` tool call as the first step of every plan, summarizing the \
incident in 1-3 sentences with appropriate severity.
- Prefer the smallest reversible action that addresses the trigger. Do not propose more \
than 3 actions per incident in v1.
- If the diagnosis is insufficient (e.g. no failover rule available for the affected \
provider), prefer notify-only and explain why in the summary.
- For latency or error-rate spikes: prefer trigger_failover when a matching rule exists.
- For cost spikes: prefer tighten_rate_limit (≤30% reduction) on the affected scope.
- For guardrail violations: prefer notify + tighten_guardrail if mode is currently \
disabled. Do NOT propose reassign_guardrail or budget freezes without strong evidence.
- Never invent UUIDs. Pull failover_rule_id, policy_id, guardrail_id, team_id from the \
diagnosis fields where available.

Output: a sequence of tool calls. Do not produce conversational text outside tool calls.
"""


class LLMProposer:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def propose(self, diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return a list of {action, params} dicts. Empty list = no remediation proposed."""
        tools = actions.list_tool_definitions()

        user_prompt = (
            "Incident diagnosis (JSON):\n```json\n"
            + json.dumps(diagnosis, indent=2, default=str)
            + "\n```\n\nPropose a remediation plan as tool calls."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tools,
                tool_choice="auto",
                temperature=0.0,
                max_tokens=2000,
            )
        except Exception as e:
            logger.warning("LLM proposer failed: %s", e)
            return [
                {
                    "action": "notify",
                    "params": {
                        "summary": f"SRE agent could not reach the LLM. Manual review required for {diagnosis.get('trigger_event')}.",
                        "severity": "warning",
                    },
                }
            ]

        choice = response.choices[0] if response.choices else None
        tool_calls = (choice.message.tool_calls if choice and choice.message else None) or []

        proposed: List[Dict[str, Any]] = []
        for call in tool_calls:
            name = call.function.name
            try:
                params = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                params = {}
            err = actions.validate(name, params)
            if err:
                logger.warning("Rejected LLM tool call: %s", err)
                continue
            proposed.append({"action": name, "params": params})

        if not proposed:
            # LLM produced no valid tool calls; default to notify-only.
            proposed.append(
                {
                    "action": "notify",
                    "params": {
                        "summary": f"SRE agent received {diagnosis.get('trigger_event')} but the LLM did not propose a valid remediation. Manual review required.",
                        "severity": "warning",
                    },
                }
            )
        return proposed


def build_proposer() -> LLMProposer:
    return LLMProposer(
        base_url=os.getenv("LITELLM_URL", "http://litellm:4000") + "/v1",
        api_key=os.getenv("SRE_AGENT_API_KEY") or os.getenv("LITELLM_MASTER_KEY", ""),
        model=os.getenv("SRE_AGENT_MODEL", "claude-sonnet-4-6"),
    )
