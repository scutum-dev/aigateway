"""DLP content detector management router."""

import json
import re
from typing import List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ContentDetectorCreate(BaseModel):
    name: str
    description: Optional[str] = None
    detector_type: str
    config: dict = {}


class ContentDetectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    detector_type: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None


class ContentDetector(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    detector_type: str
    config: dict = {}
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DetectorTestRequest(BaseModel):
    text: str


class DetectorTestResult(BaseModel):
    matches: list = []


class TeamContentPolicyCreate(BaseModel):
    policy_type: str
    config: dict = {}


class TeamContentPolicy(BaseModel):
    id: str
    team_id: str
    policy_type: str
    config: dict = {}
    is_active: bool = True
    created_at: Optional[str] = None


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
                    matches.append({
                        "label": label,
                        "match": m.group(),
                        "start": m.start(),
                        "end": m.end(),
                    })
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
                matches.append({
                    "label": "keyword",
                    "match": text[idx:idx + len(kw)],
                    "start": idx,
                    "end": idx + len(kw),
                })
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
                matches.append({
                    "label": entity_type,
                    "match": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                })

    return matches


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
