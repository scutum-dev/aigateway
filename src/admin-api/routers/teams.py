from typing import List

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from models import Team, TeamCreate, TeamMember, TeamUpdate

router = APIRouter()


async def _row_to_team(conn, row) -> Team:
    members = await conn.fetch("SELECT user_id FROM team_members WHERE team_id = $1", row["id"])
    return Team(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        monthly_budget=float(row["monthly_budget"]) if row["monthly_budget"] else None,
        default_model=row["default_model"],
        members=[m["user_id"] for m in members],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/teams", response_model=List[Team])
async def list_teams(user: UserInfo = Depends(get_current_user)):
    """List all teams."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM teams ORDER BY name")
        return [await _row_to_team(conn, row) for row in rows]


@router.post("/teams", response_model=Team)
async def create_team(team: TeamCreate, user: UserInfo = Depends(require_admin)):
    """Create a new team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO teams (name, description, monthly_budget, default_model)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """,
            team.name,
            team.description,
            team.monthly_budget,
            team.default_model,
        )

        return await _row_to_team(conn, row)


@router.put("/teams/{team_id}", response_model=Team)
async def update_team(
    team_id: str,
    update: TeamUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update a team."""
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

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(team_id)

    query = f"""
        UPDATE teams
        SET {", ".join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Team not found")
        return await _row_to_team(conn, row)


@router.delete("/teams/{team_id}")
async def delete_team(
    team_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Delete a team and clean up guardrail assignments."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute("DELETE FROM team_guardrails WHERE team_id = $1", team_id)
        await conn.execute("DELETE FROM team_members WHERE team_id = $1", team_id)
        result = await conn.execute("DELETE FROM teams WHERE id = $1", team_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Team not found")

    return {"status": "deleted"}


@router.post("/teams/{team_id}/members")
async def add_team_member(team_id: str, member: TeamMember, user: UserInfo = Depends(require_admin)):
    """Add a member to a team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO team_members (team_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, user_id) DO UPDATE SET role = $3
        """,
            team_id,
            member.user_id,
            member.role,
        )

    return {"status": "added"}
