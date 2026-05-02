# Pre-GTM Roadmap — closing the gap between landing-page claims and shipping code

This is the engineering work needed before the landing page (and any sales call)
is fully defensible. Anything not on this list is either **shipped** today or
**deliberately scoped out** of v1. Items are grouped by effort and ordered by
sales blast radius.

Source of this list: gap analysis between `ui/landing/index.html` (current copy
after the 2026-05 honesty pass) and the actual codebase. Cross-checked against
the feature audit in `docs/`.

## Tier 0 — ship in a week, removes "soften the copy" tax

These are small, well-scoped, and let you upgrade specific claims back to
unconditional language on the landing page.

| Item | Effort | Removes which softening |
|---|---|---|
| **Audit retention enforcement** | ~1 day | "configurable retention" → "1-year / 7-year retention enforced" |
| **CSV/JSON audit export** | ~half day (verify if already partially built) | "CSV/JSON export" claim is now safe |
| **Cosign-signed container images in CI** | ~half day if a release pipeline exists; ~2 days from scratch | Restore "signed container images" line in FAQ |
| **License key + seat-count check** (env-based, not full DRM) | ~2 days | "Up to 25 team members" pricing claim becomes enforceable |
| **30-day trial expiry + auto-downgrade** | ~2 days (builds on license check) | Free Trial tier becomes a real product feature, not just marketing |

**Implementation notes:**
- Audit retention: background task in admin-api, reads `platform_settings.audit_retention_days` (per-tier default), runs nightly `DELETE FROM audit_logs WHERE timestamp < now() - retention_days`. Add migration with sane defaults: 90d Team, 365d Business, configurable Enterprise.
- License check: signed JWT with `tier`, `seat_count`, `expires_at` claims. Mounted as env or file. `admin-api` validates on startup + every key/team mutation. Hard-fail at boundary; soft-warn within 7 days of expiry.
- Trial expiry: when license `tier == "trial"` and now > `expires_at`, flip platform to read-only mode (POST/PUT/DELETE return 402 Payment Required, GETs work). Send notification 7d / 1d before via existing event-publisher Slack channel.

## Tier 1 — ship in a month, unlocks enterprise pitches

These are medium projects that close real product gaps. They're explicitly
called out as "on roadmap" on the current page.

| Item | Effort | Unlocks |
|---|---|---|
| **SAML SSO** (in addition to existing OIDC) | ~1 week with `python3-saml` library | Drops the "SAML on roadmap" hedge in the SSO bullet |
| **SCIM 2.0 provisioning** | ~2-3 weeks for spec-compliant `/Users` and `/Groups` endpoints | Adds back the SCIM line in Enterprise pricing card |
| **Cedar-backed admin RBAC** (extending Cedar from agentgateway-only to admin-api) | ~2 weeks | Lets us say "Cedar policy enforcement" without the routing-only caveat |
| **Air-gapped install bundle** (offline license validation + signed artifact mirroring) | ~3 weeks | Adds back the air-gapped claim for Enterprise |

**Implementation notes:**
- SAML: `python3-saml` is the standard. Add `auth_saml.py` mirroring `auth_sso.py`. Per-org IdP metadata stored in `org_sso_providers` table (already exists for OIDC). Test against Okta, Azure AD, Google.
- SCIM: implement `/scim/v2/Users` (CRUD) and `/scim/v2/Groups`. Most enterprise IdPs use a pretty narrow subset of the spec — start with that. Library: `django-scim2` patterns translate to FastAPI; or write the ~500 lines manually.
- Cedar admin RBAC: replace the `is_admin` boolean checks in `routers/*.py` with `cedar.is_authorized(user, action, resource, context)` calls. Existing `config/agentgateway/policies/rbac.cedar` is a starting template. Adds 1-2ms per request.
- Air-gapped: `cosign verify` in `_run_migrations()` startup; mirror images to user's registry via `oras` or `skopeo`; license key includes the registry hostname.

## Tier 2 — months, organizational not technical

| Item | What it really takes |
|---|---|
| **SOC2 Type I** | ~6 months, ~$30-40k. Drata / Vanta to manage controls. Re-enables "SOC2 audit complete" in copy. |
| **SOC2 Type II** | Type I + 6 more months of evidence collection. ~$50-70k total. The version enterprise procurement actually wants. |
| **24/7 support staffing** | Hire on-call rotation. Not a code task. |
| **Dedicated CSM** | Hire. Not a code task. |
| **99.95% SLA** | Multi-region deploy + redundant Postgres + monitoring + on-call. Code-touchable but mainly an operations cost. |

These show up on the page as Enterprise-tier organizational commitments. They're
honest if you're prepared to staff them and deceptive if not. Each can be marked
"in progress" on the page until the underlying work happens.

## What's deliberately out of scope (for now)

- **Multi-region active-active** — single-region deploy is fine for early
  customers. Architect for it but don't build it yet.
- **Full BYO LLM marketplace** (paid model bundles) — token costs go to provider
  in v1, no need to be the merchant of record.
- **A/B testing pricing** — fixed tiers in v1.
- **Public OSS edition** — code is private (per founder decision).

## Prioritized sequence (recommended)

If forced to pick an order:

1. **Week 1** — Audit retention + license/seat check + trial expiry. Removes
   three softenings; biggest copy-wins per engineer-hour.
2. **Week 2** — Cosign signing + restore "signed images" copy.
3. **Weeks 3-5** — SAML SSO (week), then start SCIM (weeks).
4. **Week 6+** — Cedar admin RBAC. Pair with SOC2 controls work since they
   often want fine-grained authz evidence.
5. **In parallel** — kick off SOC2 Type I with a compliance-as-a-service vendor.

## Tracking

Convert each tier-0 and tier-1 item into a GitHub issue (or whatever tracker
you adopt) when the time comes. Don't pre-create them — issues that sit unworked
for months become noise. Create them at the sprint that picks them up.
