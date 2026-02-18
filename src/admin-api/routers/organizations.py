"""Organization, business unit, team hierarchy, and membership management router."""

import json
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


class OrganizationCreate(BaseModel):
    name: str = Field(..., description="Human-readable organization name")
    slug: str = Field(..., description="URL-friendly unique identifier")
    description: Optional[str] = Field(None, description="Brief description of the organization")
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = Field(None, description="Brief description of the organization")
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None
    is_active: Optional[bool] = Field(None, description="Whether the organization is active")


class Organization(BaseModel):
    id: str = Field(..., description="Unique organization identifier (UUID)")
    name: str = Field(..., description="Human-readable organization name")
    slug: str = Field(..., description="URL-friendly unique identifier")
    description: Optional[str] = Field(None, description="Brief description of the business unit")
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None
    metadata: dict = {}
    is_active: bool = True
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO 8601 last-update timestamp")
    bu_count: int = 0
    team_count: int = 0
    member_count: int = 0


class BusinessUnitCreate(BaseModel):
    name: str = Field(..., description="Business unit name")
    slug: str
    description: Optional[str] = Field(None, description="Brief description of the business unit")
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None


class BusinessUnitUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None
    is_active: Optional[bool] = Field(None, description="Whether the business unit is active")


class BusinessUnit(BaseModel):
    id: str = Field(..., description="Unique business unit identifier (UUID)")
    org_id: str = Field(..., description="Parent organization ID")
    name: str = Field(..., description="Business unit name")
    slug: str
    description: Optional[str] = None
    max_budget: Optional[float] = None
    allowed_models: Optional[List[str]] = None
    is_active: bool = True
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = None


class TeamAssign(BaseModel):
    bu_id: Optional[str] = Field(None, description="Business unit to assign team to")
    max_budget_override: Optional[float] = Field(None, description="Override max budget for this team")


class TeamHierarchy(BaseModel):
    team_id: str = Field(..., description="Team identifier")
    org_id: str = Field(..., description="Organization identifier")
    bu_id: Optional[str] = Field(None, description="Business unit identifier")
    max_budget_override: Optional[float] = Field(None, description="Override max budget for this team")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO 8601 last-update timestamp")


class OrgMemberAdd(BaseModel):
    user_id: str = Field(..., description="User identifier to add")
    role: str = Field("member", description="Organization role (admin, member, viewer)")
    bu_id: Optional[str] = Field(None, description="Business unit to assign member to")


class OrgMemberUpdate(BaseModel):
    role: str = Field(..., description="Updated organization role")


class OrgMembership(BaseModel):
    id: str = Field(..., description="Unique membership identifier (UUID)")
    user_id: str = Field(..., description="User identifier")
    email: Optional[str] = Field(None, description="Member email address")
    display_name: Optional[str] = Field(None, description="Member display name")
    org_id: str = Field(..., description="Organization identifier")
    role: str = Field(..., description="Organization role (admin, member, viewer)")
    bu_id: Optional[str] = Field(None, description="Business unit identifier")
    created_at: Optional[str] = Field(None, description="ISO 8601 join timestamp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_org(row) -> Organization:
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return Organization(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        max_budget=float(row["max_budget"]) if row["max_budget"] is not None else None,
        allowed_models=list(row["allowed_models"]) if row["allowed_models"] else None,
        metadata=meta if isinstance(meta, dict) else {},
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        bu_count=row.get("bu_count", 0) or 0,
        team_count=row.get("team_count", 0) or 0,
        member_count=row.get("member_count", 0) or 0,
    )


def _row_to_bu(row) -> BusinessUnit:
    return BusinessUnit(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        max_budget=float(row["max_budget"]) if row["max_budget"] is not None else None,
        allowed_models=list(row["allowed_models"]) if row["allowed_models"] else None,
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_team(row) -> TeamHierarchy:
    return TeamHierarchy(
        team_id=row["team_id"],
        org_id=str(row["org_id"]),
        bu_id=str(row["bu_id"]) if row["bu_id"] else None,
        max_budget_override=float(row["max_budget_override"]) if row["max_budget_override"] is not None else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_membership(row) -> OrgMembership:
    return OrgMembership(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        email=row.get("email"),
        display_name=row.get("display_name"),
        org_id=str(row["org_id"]),
        role=row["role"],
        bu_id=str(row["bu_id"]) if row["bu_id"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------


@router.get("/organizations", response_model=List[Organization])
async def list_organizations(user: UserInfo = Depends(get_current_user)):
    """List all organizations with counts."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.*,
                   COALESCE(bu.cnt, 0) AS bu_count,
                   COALESCE(th.cnt, 0) AS team_count,
                   COALESCE(om.cnt, 0) AS member_count
            FROM organizations o
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM business_units GROUP BY org_id) bu ON bu.org_id = o.id
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM team_hierarchy GROUP BY org_id) th ON th.org_id = o.id
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM org_memberships GROUP BY org_id) om ON om.org_id = o.id
            ORDER BY o.name
        """)
        return [_row_to_org(row) for row in rows]


@router.post("/organizations", response_model=Organization)
async def create_organization(
    data: OrganizationCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create a new organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO organizations (name, slug, description, max_budget, allowed_models)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *, 0 AS bu_count, 0 AS team_count, 0 AS member_count
            """,
            data.name,
            data.slug,
            data.description,
            data.max_budget,
            data.allowed_models,
        )
        org = _row_to_org(row)
        await log_audit_event(
            actor_id=user.user_id,
            action="create",
            resource_type="organization",
            resource_id=org.id,
            resource_name=org.name,
            request=request,
        )
        return org


@router.get("/organizations/{org_id}", response_model=Organization)
async def get_organization(org_id: str, user: UserInfo = Depends(get_current_user)):
    """Get organization by ID."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT o.*,
                   COALESCE(bu.cnt, 0) AS bu_count,
                   COALESCE(th.cnt, 0) AS team_count,
                   COALESCE(om.cnt, 0) AS member_count
            FROM organizations o
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM business_units WHERE org_id = $1 GROUP BY org_id) bu ON bu.org_id = o.id
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM team_hierarchy WHERE org_id = $1 GROUP BY org_id) th ON th.org_id = o.id
            LEFT JOIN (SELECT org_id, COUNT(*) AS cnt FROM org_memberships WHERE org_id = $1 GROUP BY org_id) om ON om.org_id = o.id
            WHERE o.id = $1
        """,
            org_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return _row_to_org(row)


@router.put("/organizations/{org_id}", response_model=Organization)
async def update_organization(
    org_id: str,
    data: OrganizationUpdate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Update an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    values = []
    for i, (key, val) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(val)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(org_id)

    query = f"""
        UPDATE organizations
        SET {", ".join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING *, 0 AS bu_count, 0 AS team_count, 0 AS member_count
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        await log_audit_event(
            actor_id=user.user_id,
            action="update",
            resource_type="organization",
            resource_id=org_id,
            changes=fields,
            request=request,
        )
        return _row_to_org(row)


@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Delete an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Organization not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="delete",
        resource_type="organization",
        resource_id=org_id,
        request=request,
    )
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Business Units
# ---------------------------------------------------------------------------


@router.get("/organizations/{org_id}/business-units", response_model=List[BusinessUnit])
async def list_business_units(org_id: str, user: UserInfo = Depends(get_current_user)):
    """List business units for an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM business_units WHERE org_id = $1 ORDER BY name", org_id)
        return [_row_to_bu(row) for row in rows]


@router.post("/organizations/{org_id}/business-units", response_model=BusinessUnit)
async def create_business_unit(
    org_id: str,
    data: BusinessUnitCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create a business unit within an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO business_units (org_id, name, slug, description, max_budget, allowed_models)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            org_id,
            data.name,
            data.slug,
            data.description,
            data.max_budget,
            data.allowed_models,
        )
        bu = _row_to_bu(row)
        await log_audit_event(
            actor_id=user.user_id,
            action="create",
            resource_type="business_unit",
            resource_id=bu.id,
            resource_name=bu.name,
            org_id=org_id,
            request=request,
        )
        return bu


@router.put("/organizations/{org_id}/business-units/{bu_id}", response_model=BusinessUnit)
async def update_business_unit(
    org_id: str,
    bu_id: str,
    data: BusinessUnitUpdate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Update a business unit."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    values = []
    for i, (key, val) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(val)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(bu_id)
    values.append(org_id)

    query = f"""
        UPDATE business_units
        SET {", ".join(set_clauses)}
        WHERE id = ${len(values) - 1} AND org_id = ${len(values)}
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Business unit not found")
        await log_audit_event(
            actor_id=user.user_id,
            action="update",
            resource_type="business_unit",
            resource_id=bu_id,
            changes=fields,
            org_id=org_id,
            request=request,
        )
        return _row_to_bu(row)


@router.delete("/organizations/{org_id}/business-units/{bu_id}")
async def delete_business_unit(
    org_id: str,
    bu_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Delete a business unit."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM business_units WHERE id = $1 AND org_id = $2", bu_id, org_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Business unit not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="delete",
        resource_type="business_unit",
        resource_id=bu_id,
        org_id=org_id,
        request=request,
    )
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Team Hierarchy
# ---------------------------------------------------------------------------


@router.post("/organizations/{org_id}/teams/{team_id}")
async def assign_team_to_org(
    org_id: str,
    team_id: str,
    data: TeamAssign = TeamAssign(),
    request: Request = None,
    user: UserInfo = Depends(require_admin),
):
    """Assign a team to an organization (optionally to a BU)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO team_hierarchy (team_id, org_id, bu_id, max_budget_override)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (team_id) DO UPDATE SET org_id = $2, bu_id = $3, max_budget_override = $4, updated_at = CURRENT_TIMESTAMP
            """,
            team_id,
            org_id,
            data.bu_id,
            data.max_budget_override,
        )

    await log_audit_event(
        actor_id=user.user_id,
        action="assign_team",
        resource_type="team_hierarchy",
        resource_id=team_id,
        org_id=org_id,
        request=request,
    )
    return {"status": "assigned"}


@router.delete("/organizations/{org_id}/teams/{team_id}")
async def remove_team_from_org(
    org_id: str,
    team_id: str,
    request: Request = None,
    user: UserInfo = Depends(require_admin),
):
    """Remove a team from an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM team_hierarchy WHERE team_id = $1 AND org_id = $2", team_id, org_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Team assignment not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="remove_team",
        resource_type="team_hierarchy",
        resource_id=team_id,
        org_id=org_id,
        request=request,
    )
    return {"status": "removed"}


@router.get("/organizations/{org_id}/teams", response_model=List[TeamHierarchy])
async def list_org_teams(org_id: str, user: UserInfo = Depends(get_current_user)):
    """List teams assigned to an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM team_hierarchy WHERE org_id = $1 ORDER BY team_id", org_id)
        return [_row_to_team(row) for row in rows]


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------


@router.get("/organizations/{org_id}/members", response_model=List[OrgMembership])
async def list_org_members(org_id: str, user: UserInfo = Depends(get_current_user)):
    """List members of an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT om.*, u.email, u.display_name
            FROM org_memberships om
            LEFT JOIN users u ON u.id = om.user_id
            WHERE om.org_id = $1
            ORDER BY om.created_at
        """,
            org_id,
        )
        return [_row_to_membership(row) for row in rows]


@router.post("/organizations/{org_id}/members", response_model=OrgMembership)
async def add_org_member(
    org_id: str,
    data: OrgMemberAdd,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Add a member to an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO org_memberships (user_id, org_id, role, bu_id)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            data.user_id,
            org_id,
            data.role,
            data.bu_id,
        )
        await log_audit_event(
            actor_id=user.user_id,
            action="add_member",
            resource_type="org_membership",
            resource_id=str(row["id"]),
            org_id=org_id,
            changes={"user_id": data.user_id, "role": data.role},
            request=request,
        )
        return _row_to_membership(row)


@router.put("/organizations/{org_id}/members/{member_user_id}")
async def update_org_member(
    org_id: str,
    member_user_id: str,
    data: OrgMemberUpdate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Update a member's role in an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE org_memberships SET role = $1
            WHERE user_id = $2 AND org_id = $3
            """,
            data.role,
            member_user_id,
            org_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Membership not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="update_member_role",
        resource_type="org_membership",
        resource_id=member_user_id,
        org_id=org_id,
        changes={"role": data.role},
        request=request,
    )
    return {"status": "updated"}


@router.delete("/organizations/{org_id}/members/{member_user_id}")
async def remove_org_member(
    org_id: str,
    member_user_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Remove a member from an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM org_memberships WHERE user_id = $1 AND org_id = $2",
            member_user_id,
            org_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Membership not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="remove_member",
        resource_type="org_membership",
        resource_id=member_user_id,
        org_id=org_id,
        request=request,
    )
    return {"status": "removed"}
