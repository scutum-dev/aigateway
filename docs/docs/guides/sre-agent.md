# SRE Agent

LLM-driven incident remediation with human-in-loop approval. The SRE agent watches platform events, proposes remediations, and executes them only after a human approves — risk-scored 0–100 so trivial actions can be auto-approved while anything destructive is gated.

> **Tier**: Available on **Business** and **Enterprise** licenses. Not included in Trial or Team.

## How it works

```
incident event ──► SRE agent ──► proposed action ──► risk score
                                       │
                          ┌────────────┴───────────┐
                  score ≤ threshold        score > threshold
                          │                         │
                  auto-execute (if              push to operator
                  SRE_AUTO_APPROVE)             via Slack/email/UI
                                                    │
                                              operator approves ──► execute
                                                    │
                                              operator rejects ──► log + close
```

The agent reasons about the incident with a configured LLM (default `claude-sonnet-4-6`), proposes a concrete action from the action library (e.g., "circuit-break provider X for 5 minutes", "raise rate limit for team Y", "page on-call"), assigns a risk score, and routes it appropriately.

## Trigger events

The agent subscribes to four event types from admin-api's event bus:

| Event | Fires when |
|---|---|
| `provider.unhealthy` | Error rate exceeds 25% across 5+ requests in a 5-minute window |
| `budget.exceeded` | A team or org breaches a soft or hard budget limit |
| `sla.violation` | p95/p99 latency or success-rate target is breached for a configured SLA |
| `latency.spike` | Provider response time crosses 3× the rolling 1-hour median |

## Action library

A curated set of safe, reversible operations the agent can propose. Each action has a baseline risk score; the agent adjusts up or down based on context (time of day, blast radius, team affected, etc.).

| Action | Baseline risk | Reversible |
|---|---|---|
| Circuit-break provider for ≤ 5 min | 15 | Yes (auto-restores) |
| Re-route model group to different provider | 25 | Yes |
| Raise rate limit by ≤ 50% (one team) | 30 | Yes |
| Page on-call via PagerDuty | 35 | One-shot |
| Disable a guardrail rule | 60 | Yes |
| Bump a hard budget cap | 75 | Yes (audit trail) |
| Disable an SLA contract | 85 | Yes |

Anything score > `SRE_RISK_THRESHOLD` (default 40) requires human approval.

## Enable

The agent ships behind a Compose profile so it doesn't run on deployments that don't need it.

```bash
./scutum up --profile sre
```

Or to bring up the full stack:

```bash
./scutum up --profile full
```

Verify it's healthy:

```bash
./scutum ps | grep sre-agent
./scutum logs sre-agent
```

## Configuration

Set in `config/.env`:

```bash
# Model the agent uses to reason about incidents (must be in your routing config).
SRE_AGENT_MODEL=claude-sonnet-4-6

# Risk threshold (0-100) above which an action requires human approval.
# Lower = more conservative. Default 40 means almost everything is gated.
SRE_RISK_THRESHOLD=40

# When true, low-risk actions execute without waiting for approval.
# Default false — every action goes through human-in-loop until you've
# observed the agent for a few weeks and tuned the threshold to your taste.
SRE_AUTO_APPROVE=false
```

## Approval flow

When the agent proposes a gated action, three things happen in parallel:

1. The proposal lands in the **SRE Agent** page in the Admin Console with the full reasoning, risk score, and a one-click approve / reject.
2. A notification fires through your configured event channels — Slack, PagerDuty, email, or a webhook — with a deep-link to the proposal.
3. The proposal is logged to the audit trail with the operator who eventually approves or rejects it.

Approvals are scoped to single proposals — there's no blanket "approve all" mode. The audit trail is immutable and retained according to your license tier (30 days on Trial, 365 on Business, 7 years on Enterprise).

## Disabling

To stop the agent from running:

```bash
docker compose --env-file config/.env --profile sre stop sre-agent
```

Pending proposals stay in the queue and resume processing when the service starts again — they aren't lost.

## Audit + compliance

Every proposal, score, approval, rejection, and execution is logged to the `sre_actions` audit trail with:

- The triggering event payload
- The full LLM reasoning chain
- The risk score and which heuristics moved it
- The operator who approved/rejected
- The actual remediation result

You can export a CSV of the trail from the Admin Console → Audit Log filtered by `source: sre-agent`. SOC2 reviewers usually ask for this within 30 minutes of starting an audit; have it ready.
