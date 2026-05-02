# Licensing

Scutum is **commercial self-hosted** software. Every deployment needs a license — a signed token we issue you. Validation runs locally on your servers; nothing phones home.

## How it works

A license is an Ed25519-signed JWT containing your customer ID, contact email, organisation, tier, expiry, and feature flags. The matching public key ships with Scutum, so the admin-api verifies the token offline on every boot and on a 5-minute background timer. There is no mandatory outbound network call.

If your license is missing, expired, or tampered with, Scutum keeps running — but the Admin Console will surface a renewal banner and `/api/v1/license` returns a structured error so your tooling can react. (Hard tier-gating per feature is on the roadmap; v1 is honour-system with visible state.)

## Activate a license

You'll receive a license JWT from us via email. Two activation paths:

### Path A — environment variable (cold-boot)

```bash
# config/.env
LICENSE_KEY=eyJhbGciOiJFZERTQSI...
```

Then start the platform:

```bash
./scutum up
```

On first boot, admin-api validates the token, persists it to the `licenses` table, and uses the DB row on subsequent restarts. The env var becomes a fallback only.

### Path B — REST endpoint (refresh / rotation)

To rotate a license without restarting the platform — for example when you renew or upgrade tiers — POST the new token to the activate endpoint:

```bash
curl -X POST http://localhost:8086/api/v1/license/activate \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"license_key": "<new-jwt>"}'
```

A successful response returns the new license state. The change takes effect immediately for `/api/v1/license` responses; running requests are not interrupted.

## Inspect license state

The status endpoint is unauthenticated (so the Admin Console can read it before login):

```bash
curl http://localhost:8086/api/v1/license | jq
```

```json
{
  "present": true,
  "valid": true,
  "expired": false,
  "tier": "trial",
  "customer_email": "founder@acme.com",
  "company": "Acme Corp",
  "issued_at": "2026-05-03T08:00:00+00:00",
  "expires_at": "2026-06-02T08:00:00+00:00",
  "days_remaining": 29,
  "features": {
    "max_admins": 5,
    "mcp_servers": true,
    "workflows": true,
    "sso": false,
    "audit_retention_days": 30
  },
  "error": null
}
```

The response **never** contains the JWT itself or any signing material. Safe to expose to internal monitoring.

## Tiers

| Tier | Typical scope | Default features |
|---|---|---|
| **Trial** | 30-day evaluation | Up to 5 admins, all features unlocked, 30-day audit retention |
| **Team** | Single product team | Up to 10 admins, no SRE agent, no SSO, 90-day audit retention |
| **Business** | Mid-size org | Up to 50 admins, SSO + SRE agent, 365-day audit retention |
| **Enterprise** | Multi-tenant / regulated | Unlimited admins, all features, 7-year audit retention |

Feature flags are encoded in the JWT — when we issue a license at a given tier, those flags are baked in. You can audit your own license state via `/api/v1/license`.

## Renewing

We send a renewal notice 14 days before expiry. To renew:

1. Reply to the renewal email or contact [hello@scutum.dev](mailto:hello@scutum.dev).
2. We email you a fresh JWT with a new `exp` claim.
3. Activate via Path B above (no restart needed).

If you let a license lapse, Scutum keeps serving traffic — the data plane never blocks on license state. But cost reports, audit retention, SSO, and policy administration may degrade depending on your tier and the v2 enforcement rules in effect at that time.

## Troubleshooting

**`error: "license signature does not match — wrong issuer or tampered token"`**
Either the JWT was modified in transit (paste truncation is common), or someone tried to use a license issued by a different keypair. Re-paste the token. If still failing, contact us — we can re-issue.

**`error: "license expired N day(s) ago"`**
The token is otherwise valid but past its `exp`. Activate a renewed license via Path B.

**`error: "license public key not bundled with admin-api build"`**
You're running a custom-built admin-api image that doesn't include the bundled license public key. The official `ghcr.io/deosha/scutum-admin-api` images always include it; if you've forked the source and built your own, ensure `config/license-public.pem` is bundled into the build context. Contact us if you intentionally need to swap public keys.

**No license at all**
With both `LICENSE_KEY` unset and the `licenses` table empty, admin-api logs `"No license present"` on startup and the Admin Console will prompt for activation. The platform still serves traffic during this period; you have time to paste your license without an outage.
