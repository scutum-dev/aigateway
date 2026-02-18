"""DLP content detector management router."""

import json
import re
from typing import List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ContentDetectorCreate(BaseModel):
    name: str = Field(..., description="Human-readable detector name")
    description: Optional[str] = Field(None, description="Brief description of what this detector finds")
    detector_type: str = Field(..., description="Detection method: regex, keyword, or pii")
    config: dict = Field({}, description="Type-specific config (patterns, keywords, entity_types)")


class ContentDetectorUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Human-readable detector name")
    description: Optional[str] = Field(None, description="Updated description")
    detector_type: Optional[str] = Field(None, description="Detection method: regex, keyword, or pii")
    config: Optional[dict] = Field(None, description="Updated type-specific configuration")
    is_active: Optional[bool] = Field(None, description="Whether the detector is active")


class ContentDetector(BaseModel):
    id: str = Field(..., description="Unique detector identifier (UUID)")
    name: str = Field(..., description="Updated detector name")
    description: Optional[str] = Field(None, description="Brief description of what this detector finds")
    detector_type: str = Field(..., description="Updated detection method")
    config: dict = Field({}, description="Policy-specific configuration options")
    is_active: bool = Field(True, description="Whether the detector is active")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO 8601 last-update timestamp")


class DetectorTestRequest(BaseModel):
    text: str = Field(..., description="Sample text to run the detector against")


class DetectorTestResult(BaseModel):
    matches: list = Field([], description="List of detected content matches")


class TeamContentPolicyCreate(BaseModel):
    policy_type: str = Field(..., description="Policy type (block, redact, warn)")
    config: dict = Field({}, description="Policy-specific configuration options")


class TeamContentPolicy(BaseModel):
    id: str = Field(..., description="Unique content policy identifier (UUID)")
    team_id: str = Field(..., description="Team this policy is assigned to")
    policy_type: str = Field(..., description="Policy type (block, redact, warn)")
    config: dict = {}
    is_active: bool = Field(True, description="Whether the policy is active")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_detector(row) -> ContentDetector:
    config = row["config"]
    if isinstance(config, str):
        config = json.loads(config)
    return ContentDetector(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        detector_type=row["detector_type"],
        config=config if isinstance(config, dict) else {},
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_policy(row) -> TeamContentPolicy:
    config = row["config"]
    if isinstance(config, str):
        config = json.loads(config)
    return TeamContentPolicy(
        id=str(row["id"]),
        team_id=str(row["team_id"]),
        policy_type=row["policy_type"],
        config=config if isinstance(config, dict) else {},
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _run_detector(detector_type: str, config: dict, text: str) -> list:
    """Run a simple content detector against text. Returns list of matches."""
    matches = []

    if detector_type == "regex":
        patterns = config.get("patterns", [])
        for pattern_entry in patterns:
            pattern = pattern_entry if isinstance(pattern_entry, str) else pattern_entry.get("pattern", "")
            label = pattern_entry if isinstance(pattern_entry, str) else pattern_entry.get("label", pattern)
            try:
                for m in re.finditer(pattern, text):
                    matches.append(
                        {
                            "label": label,
                            "match": m.group(),
                            "start": m.start(),
                            "end": m.end(),
                        }
                    )
            except re.error:
                pass

    elif detector_type == "keyword":
        keywords = config.get("keywords", [])
        for kw in keywords:
            lower_text = text.lower()
            lower_kw = kw.lower()
            start = 0
            while True:
                idx = lower_text.find(lower_kw, start)
                if idx == -1:
                    break
                matches.append(
                    {
                        "label": "keyword",
                        "match": text[idx : idx + len(kw)],
                        "start": idx,
                        "end": idx + len(kw),
                    }
                )
                start = idx + 1

    elif detector_type == "pii":
        # Simple built-in PII patterns
        pii_patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }
        enabled_types = config.get("entity_types", list(pii_patterns.keys()))
        for entity_type in enabled_types:
            pattern = pii_patterns.get(entity_type)
            if not pattern:
                continue
            for m in re.finditer(pattern, text):
                matches.append(
                    {
                        "label": entity_type,
                        "match": m.group(),
                        "start": m.start(),
                        "end": m.end(),
                    }
                )

    return matches


async def scan_text_with_detectors(text: str, team_id: str = None, guardrail_id: str = None) -> dict:
    """Run all relevant detectors against text. Returns {clean, matches, blocked, block_reasons}.

    If guardrail_id is provided, only run detectors attached to that guardrail.
    Otherwise, run all active detectors. Also checks team content policies if team_id is given.
    """
    result = {"clean": True, "matches": [], "blocked": False, "block_reasons": []}

    if not deps.db_pool:
        return result

    async with deps.db_pool.acquire() as conn:
        # Load detectors
        if guardrail_id:
            rows = await conn.fetch(
                """
                SELECT cd.* FROM content_detectors cd
                JOIN guardrail_detectors gd ON gd.detector_id = cd.id
                WHERE gd.guardrail_config_id = $1 AND cd.is_active = true
                ORDER BY gd.priority
                """,
                guardrail_id,
            )
        else:
            rows = await conn.fetch("SELECT * FROM content_detectors WHERE is_active = true ORDER BY name")

        for row in rows:
            detector = _row_to_detector(row)
            matches = _run_detector(detector.detector_type, detector.config, text)
            if matches:
                result["clean"] = False
                for m in matches:
                    m["detector_name"] = detector.name
                    m["detector_id"] = detector.id
                result["matches"].extend(matches)

                # Check if any pattern has action=block
                cfg = detector.config
                if detector.detector_type == "regex":
                    for p in cfg.get("patterns", []):
                        if isinstance(p, dict) and p.get("action") == "block":
                            result["blocked"] = True
                            result["block_reasons"].append(f"Detector '{detector.name}' blocked content")
                            break
                elif detector.detector_type == "pii":
                    # PII detectors with action=block in config
                    if cfg.get("action") == "block":
                        result["blocked"] = True
                        result["block_reasons"].append(f"PII detector '{detector.name}' blocked content")

        # Check team content policies
        if team_id:
            policies = await conn.fetch(
                "SELECT * FROM team_content_policies WHERE team_id = $1 AND is_active = true",
                team_id,
            )
            for policy in policies:
                cfg = policy["config"]
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                policy_type = policy["policy_type"]

                if policy_type == "block":
                    blocked_keywords = cfg.get("keywords", [])
                    for kw in blocked_keywords:
                        if kw.lower() in text.lower():
                            result["clean"] = False
                            result["blocked"] = True
                            result["matches"].append({"label": "blocked_keyword", "match": kw})
                            result["block_reasons"].append(f"Team policy blocks keyword: {kw}")

                elif policy_type == "warn":
                    warn_keywords = cfg.get("keywords", [])
                    for kw in warn_keywords:
                        if kw.lower() in text.lower():
                            result["clean"] = False
                            result["matches"].append({"label": "warn_keyword", "match": kw})

    return result


class ScanRequest(BaseModel):
    text: str = Field(..., description="Text to scan for sensitive content")
    team_id: Optional[str] = Field(None, description="Optional team ID to check team content policies")
    guardrail_id: Optional[str] = Field(None, description="Optional guardrail ID to use only its attached detectors")


@router.post("/scan")
async def scan_text(data: ScanRequest, user: UserInfo = Depends(get_current_user)):
    """Scan text against all active DLP detectors and team content policies."""
    result = await scan_text_with_detectors(
        text=data.text,
        team_id=data.team_id,
        guardrail_id=data.guardrail_id,
    )
    return result


# ---------------------------------------------------------------------------
# Content Detector CRUD
# ---------------------------------------------------------------------------


@router.get("/detectors", response_model=List[ContentDetector])
async def list_detectors(user: UserInfo = Depends(get_current_user)):
    """List all content detectors."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM content_detectors ORDER BY name")
        return [_row_to_detector(row) for row in rows]


@router.post("/detectors", response_model=ContentDetector)
async def create_detector(
    data: ContentDetectorCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create a new content detector."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO content_detectors (name, description, detector_type, config)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            data.name,
            data.description,
            data.detector_type,
            json.dumps(data.config),
        )
        detector = _row_to_detector(row)
        await log_audit_event(
            actor_id=user.user_id,
            action="create",
            resource_type="content_detector",
            resource_id=detector.id,
            resource_name=detector.name,
            request=request,
        )
        return detector


@router.get("/detectors/{detector_id}", response_model=ContentDetector)
async def get_detector(detector_id: str, user: UserInfo = Depends(get_current_user)):
    """Get a content detector by ID."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM content_detectors WHERE id = $1", detector_id)
        if not row:
            raise HTTPException(status_code=404, detail="Detector not found")
        return _row_to_detector(row)


@router.put("/detectors/{detector_id}", response_model=ContentDetector)
async def update_detector(
    detector_id: str,
    data: ContentDetectorUpdate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Update a content detector."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    values = []
    for i, (key, val) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        if key == "config":
            values.append(json.dumps(val))
        else:
            values.append(val)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(detector_id)

    query = f"""
        UPDATE content_detectors
        SET {", ".join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Detector not found")
        await log_audit_event(
            actor_id=user.user_id,
            action="update",
            resource_type="content_detector",
            resource_id=detector_id,
            changes=fields,
            request=request,
        )
        return _row_to_detector(row)


@router.delete("/detectors/{detector_id}")
async def delete_detector(
    detector_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Delete a content detector."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM content_detectors WHERE id = $1", detector_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Detector not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="delete",
        resource_type="content_detector",
        resource_id=detector_id,
        request=request,
    )
    return {"status": "deleted"}


@router.post("/detectors/{detector_id}/test", response_model=DetectorTestResult)
async def test_detector(
    detector_id: str,
    data: DetectorTestRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Test a content detector against sample text."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM content_detectors WHERE id = $1", detector_id)
        if not row:
            raise HTTPException(status_code=404, detail="Detector not found")

    detector = _row_to_detector(row)
    matches = _run_detector(detector.detector_type, detector.config, data.text)
    return DetectorTestResult(matches=matches)


# ---------------------------------------------------------------------------
# Guardrail-Detector linking
# ---------------------------------------------------------------------------


@router.post("/guardrails/{guardrail_id}/detectors/{detector_id}")
async def attach_detector_to_guardrail(
    guardrail_id: str,
    detector_id: str,
    priority: int = 0,
    request: Request = None,
    user: UserInfo = Depends(require_admin),
):
    """Attach a content detector to a guardrail configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO guardrail_detectors (guardrail_config_id, detector_id, priority)
            VALUES ($1, $2, $3)
            ON CONFLICT (guardrail_config_id, detector_id) DO UPDATE SET priority = $3
            """,
            guardrail_id,
            detector_id,
            priority,
        )

    await log_audit_event(
        actor_id=user.user_id,
        action="attach_detector",
        resource_type="guardrail_detector",
        resource_id=f"{guardrail_id}:{detector_id}",
        request=request,
    )
    return {"status": "attached"}


@router.delete("/guardrails/{guardrail_id}/detectors/{detector_id}")
async def detach_detector_from_guardrail(
    guardrail_id: str,
    detector_id: str,
    request: Request = None,
    user: UserInfo = Depends(require_admin),
):
    """Detach a content detector from a guardrail configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM guardrail_detectors WHERE guardrail_config_id = $1 AND detector_id = $2",
            guardrail_id,
            detector_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Detector attachment not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="detach_detector",
        resource_type="guardrail_detector",
        resource_id=f"{guardrail_id}:{detector_id}",
        request=request,
    )
    return {"status": "detached"}


# ---------------------------------------------------------------------------
# Team Content Policies
# ---------------------------------------------------------------------------


@router.get("/teams/{team_id}/content-policies", response_model=List[TeamContentPolicy])
async def list_team_content_policies(
    team_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """List content policies for a team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM team_content_policies WHERE team_id = $1 ORDER BY policy_type",
            team_id,
        )
        return [_row_to_policy(row) for row in rows]


@router.put("/teams/{team_id}/content-policies", response_model=TeamContentPolicy)
async def create_or_update_team_content_policy(
    team_id: str,
    data: TeamContentPolicyCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create or update a team content policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO team_content_policies (team_id, policy_type, config)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, policy_type) DO UPDATE SET
                config = EXCLUDED.config,
                is_active = TRUE
            RETURNING *
            """,
            team_id,
            data.policy_type,
            json.dumps(data.config),
        )
        policy = _row_to_policy(row)
        await log_audit_event(
            actor_id=user.user_id,
            action="update_content_policy",
            resource_type="team_content_policy",
            resource_id=policy.id,
            changes={"policy_type": data.policy_type},
            request=request,
        )
        return policy
