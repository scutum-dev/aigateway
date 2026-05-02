#!/usr/bin/env python3
"""Mint a Scutum license JWT signed with the issuer's Ed25519 private key.

Run locally on the issuer's laptop. The private key MUST live outside the
repo (default: ~/.scutum/license-private.pem, gitignored). The matching
public key — config/license-public.pem — ships in the repo so admin-api
can validate.

Examples:

    # 30-day trial for a customer
    python scripts/issue-license.py \\
        --email founder@acme.com --company "Acme Corp" --tier trial --days 30

    # Annual paid license
    python scripts/issue-license.py \\
        --email ops@bigco.com --company "BigCo" --tier business --days 365

    # Print just the JWT (no banner) — pipe-friendly for automation
    python scripts/issue-license.py --email x@y.com --tier trial --days 30 --quiet

The output is a single JWT line that the customer pastes into their
LICENSE_KEY env var (or POSTs to /api/v1/license/activate).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import jwt as pyjwt
except ImportError:
    sys.stderr.write("Missing dependency: pyjwt. Install with `pip install 'pyjwt[crypto]>=2.8'`\n")
    sys.exit(1)


TIER_DEFAULT_FEATURES = {
    "trial": {
        "max_admins": 5,
        "max_models": None,
        "mcp_servers": True,
        "workflows": True,
        "sre_agent": True,
        "sso": False,
        "audit_retention_days": 30,
    },
    "team": {
        "max_admins": 10,
        "max_models": None,
        "mcp_servers": True,
        "workflows": True,
        "sre_agent": False,
        "sso": False,
        "audit_retention_days": 90,
    },
    "business": {
        "max_admins": 50,
        "max_models": None,
        "mcp_servers": True,
        "workflows": True,
        "sre_agent": True,
        "sso": True,
        "audit_retention_days": 365,
    },
    "enterprise": {
        "max_admins": None,
        "max_models": None,
        "mcp_servers": True,
        "workflows": True,
        "sre_agent": True,
        "sso": True,
        "audit_retention_days": 2555,  # 7 years
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True, help="Customer's primary contact email")
    p.add_argument("--company", default="", help="Customer organisation name")
    p.add_argument(
        "--tier",
        default="trial",
        choices=list(TIER_DEFAULT_FEATURES.keys()),
        help="License tier (default: trial)",
    )
    p.add_argument("--days", type=int, default=30, help="Days until expiry (default: 30)")
    p.add_argument(
        "--customer-id",
        default=None,
        help="Stable customer identifier. Defaults to a fresh UUID.",
    )
    p.add_argument(
        "--features-json",
        default=None,
        help="Optional JSON string overriding default features for this tier",
    )
    p.add_argument(
        "--private-key",
        default=os.path.expanduser("~/.scutum/license-private.pem"),
        help="Path to the Ed25519 private key (default: ~/.scutum/license-private.pem)",
    )
    p.add_argument("--quiet", action="store_true", help="Print only the JWT, no banner")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    private_key_path = Path(args.private_key)
    if not private_key_path.exists():
        sys.stderr.write(
            f"Private key not found at {private_key_path}.\n"
            f"Generate one with:\n"
            f"  mkdir -p ~/.scutum && \\\n"
            f"  openssl genpkey -algorithm ed25519 -out ~/.scutum/license-private.pem && \\\n"
            f"  openssl pkey -in ~/.scutum/license-private.pem -pubout -out config/license-public.pem\n"
        )
        return 1

    with open(private_key_path, "rb") as f:
        private_key = f.read()

    customer_id = args.customer_id or f"cust_{uuid.uuid4().hex[:12]}"

    if args.features_json:
        try:
            features = json.loads(args.features_json)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Invalid --features-json: {e}\n")
            return 1
    else:
        features = TIER_DEFAULT_FEATURES[args.tier]

    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=args.days)

    claims = {
        "sub": customer_id,
        "email": args.email,
        "company": args.company,
        "tier": args.tier,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "features": features,
    }

    token = pyjwt.encode(claims, private_key, algorithm="EdDSA")

    if not args.quiet:
        sys.stderr.write(
            "─────────────────────────────────────────────────────────────────\n"
            f" Scutum license issued\n"
            f"  customer_id: {customer_id}\n"
            f"  email:       {args.email}\n"
            f"  company:     {args.company or '(none)'}\n"
            f"  tier:        {args.tier}\n"
            f"  issued:      {now.isoformat()}\n"
            f"  expires:     {exp.isoformat()} ({args.days} days)\n"
            f"  features:    {json.dumps(features, indent=15)[:80]}...\n"
            "─────────────────────────────────────────────────────────────────\n"
            "Customer activates by either:\n"
            "  1. Setting LICENSE_KEY in config/.env to the token below, OR\n"
            '  2. POST /api/v1/license/activate with {"license_key": "<token>"}\n'
            "─────────────────────────────────────────────────────────────────\n"
        )

    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
