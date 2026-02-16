"""Guardrail configuration and event management router."""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

import deps
from auth import get_current_user, require_admin, UserInfo

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GuardrailConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    enable_prompt_injection: bool = True
    prompt_injection_threshold: float = 0.90
    enable_pii_detection: bool = True
    pii_action: str = "anonymize"
    pii_entities: List[str] = Field(default_factory=lambda: [
        "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
        "US_SSN", "IBAN_CODE", "IP_ADDRESS",
    ])
    enable_toxicity: bool = True
    toxicity_threshold: float = 0.70
    banned_topics: List[str] = Field(default_factory=list)
    enable_secrets_detection: bool = True
    enable_invisible_text: bool = True
    enable_malicious_urls: bool = True
    enable_sensitive_output: bool = True
    mode: str = "block"
    on_fail: str = "block"
    is_active: bool = True


class GuardrailConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enable_prompt_injection: Optional[bool] = None
    prompt_injection_threshold: Optional[float] = None
    enable_pii_detection: Optional[bool] = None
    pii_action: Optional[str] = None
    pii_entities: Optional[List[str]] = None
    enable_toxicity: Optional[bool] = None
    toxicity_threshold: Optional[float] = None
    banned_topics: Optional[List[str]] = None
    enable_secrets_detection: Optional[bool] = None
    enable_invisible_text: Optional[bool] = None
    enable_malicious_urls: Optional[bool] = None
    enable_sensitive_output: Optional[bool] = None
    mode: Optional[str] = None
    on_fail: Optional[str] = None
    is_active: Optional[bool] = None


class GuardrailConfig(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    enable_prompt_injection: bool
    prompt_injection_threshold: float
    enable_pii_detection: bool
    pii_action: str
    pii_entities: List[str]
    enable_toxicity: bool
    toxicity_threshold: float
    banned_topics: List[str]
    enable_secrets_detection: bool
    enable_invisible_text: bool
    enable_malicious_urls: bool
    enable_sensitive_output: bool
    mode: str
    on_fail: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GuardrailAssignment(BaseModel):
    team_id: str
    team_name: str
    guardrail_config_id: str
    config_name: str
    priority: int = 0


class GuardrailEvent(BaseModel):
    id: str
    event_type: str
    scanner_name: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    model: Optional[str] = None
    risk_score: Optional[float] = None
    action_taken: str
    details: dict = {}
    created_at: Optional[str] = None



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_config(row) -> GuardrailConfig:
    return GuardrailConfig(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        enable_prompt_injection=row["enable_prompt_injection"],
        prompt_injection_threshold=float(row["prompt_injection_threshold"]),
        enable_pii_detection=row["enable_pii_detection"],
        pii_action=row["pii_action"],
        pii_entities=list(row["pii_entities"] or []),
        enable_toxicity=row["enable_toxicity"],
        toxicity_threshold=float(row["toxicity_threshold"]),
        banned_topics=list(row["banned_topics"] or []),
        enable_secrets_detection=row["enable_secrets_detection"],
        enable_invisible_text=row["enable_invisible_text"],
        enable_malicious_urls=row["enable_malicious_urls"],
        enable_sensitive_output=row["enable_sensitive_output"],
        mode=row["mode"],
        on_fail=row["on_fail"],
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_event(row) -> GuardrailEvent:
    details = row["details"]
    if isinstance(details, str):
        details = json.loads(details)
    return GuardrailEvent(
        id=str(row["id"]),
        event_type=row["event_type"],
        scanner_name=row["scanner_name"],
        user_id=row["user_id"],
        team_id=row["team_id"],
        model=row["model"],
        risk_score=float(row["risk_score"]) if row["risk_score"] is not None else None,
        action_taken=row["action_taken"],
        details=details if isinstance(details, dict) else {},
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/guardrails", response_model=List[GuardrailConfig])
async def list_guardrail_configs(user: UserInfo = Depends(get_current_user)):
    """List all guardrail configurations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM guardrail_configs ORDER BY name")
        return [_row_to_config(row) for row in rows]


@router.post("/guardrails", response_model=GuardrailConfig)
async def create_guardrail_config(
    config: GuardrailConfigCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a new guardrail configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO guardrail_configs (
                name, description,
                enable_prompt_injection, prompt_injection_threshold,
                enable_pii_detection, pii_action, pii_entities,
                enable_toxicity, toxicity_threshold, banned_topics,
                enable_secrets_detection, enable_invisible_text,
                enable_malicious_urls, enable_sensitive_output,
                mode, on_fail, is_active
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            RETURNING *
        """,
            config.name, config.description,
            config.enable_prompt_injection, config.prompt_injection_threshold,
            config.enable_pii_detection, config.pii_action, config.pii_entities,
            config.enable_toxicity, config.toxicity_threshold, config.banned_topics,
            config.enable_secrets_detection, config.enable_invisible_text,
            config.enable_malicious_urls, config.enable_sensitive_output,
            config.mode, config.on_fail, config.is_active,
        )
        return _row_to_config(row)


@router.get("/guardrails/{config_id}", response_model=GuardrailConfig)
async def get_guardrail_config(
    config_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get a guardrail configuration by ID."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM guardrail_configs WHERE id = $1", config_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Guardrail config not found")
        return _row_to_config(row)


@router.put("/guardrails/{config_id}", response_model=GuardrailConfig)
async def update_guardrail_config(
    config_id: str,
    update: GuardrailConfigUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update a guardrail configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    fields = update.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    values = []
    for i, (key, val) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(val)

    set_clauses.append(f"updated_at = CURRENT_TIMESTAMP")
    values.append(config_id)

    query = f"""
        UPDATE guardrail_configs
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Guardrail config not found")
        return _row_to_config(row)


@router.delete("/guardrails/{config_id}")
async def delete_guardrail_config(
    config_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Delete a guardrail configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM guardrail_configs WHERE id = $1", config_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Guardrail config not found")

    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Team assignment
# ---------------------------------------------------------------------------

@router.post("/guardrails/{config_id}/assign/{team_id}")
async def assign_guardrail_to_team(
    config_id: str,
    team_id: str,
    priority: int = Query(default=0),
    user: UserInfo = Depends(require_admin),
):
    """Assign a guardrail config to a team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO team_guardrails (team_id, guardrail_config_id, priority)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, guardrail_config_id) DO UPDATE SET priority = $3
        """, team_id, config_id, priority)

    return {"status": "assigned"}


@router.get("/guardrail-assignments", response_model=List[GuardrailAssignment])
async def list_guardrail_assignments(
    user: UserInfo = Depends(get_current_user),
):
    """List all team-guardrail assignments."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT tg.team_id, t.name AS team_name,
                   tg.guardrail_config_id, gc.name AS config_name,
                   tg.priority
            FROM team_guardrails tg
            JOIN teams t ON t.id = tg.team_id
            JOIN guardrail_configs gc ON gc.id = tg.guardrail_config_id
            ORDER BY t.name, gc.name
        """)
        return [
            GuardrailAssignment(
                team_id=str(row["team_id"]),
                team_name=row["team_name"],
                guardrail_config_id=str(row["guardrail_config_id"]),
                config_name=row["config_name"],
                priority=row["priority"],
            )
            for row in rows
        ]


@router.delete("/guardrails/{config_id}/assign/{team_id}")
async def unassign_guardrail_from_team(
    config_id: str,
    team_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Unassign a guardrail config from a team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM team_guardrails
            WHERE team_id = $1 AND guardrail_config_id = $2
        """, team_id, config_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Assignment not found")

    return {"status": "unassigned"}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@router.get("/guardrail-events", response_model=List[GuardrailEvent])
async def list_guardrail_events(
    team_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserInfo = Depends(get_current_user),
):
    """List guardrail events with optional filtering."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = []
    params: list = []
    idx = 1

    if team_id:
        conditions.append(f"team_id = ${idx}")
        params.append(team_id)
        idx += 1
    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.append(limit)
    params.append(offset)

    query = f"""
        SELECT * FROM guardrail_events
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_event(row) for row in rows]


