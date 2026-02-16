from typing import List

from fastapi import APIRouter, HTTPException, Depends

import deps
from auth import get_current_user, require_admin, UserInfo
from models import Team, TeamCreate, TeamMember

router = APIRouter()


@router.get("/teams", response_model=List[Team])
async def list_teams(user: UserInfo = Depends(get_current_user)):
    """List all teams."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM teams ORDER BY name")
        teams = []
        for row in rows:
            members = await conn.fetch(
                "SELECT user_id FROM team_members WHERE team_id = $1",
                row["id"]
            )
            teams.append(Team(
                id=str(row["id"]),
                name=row["name"],
                description=row["description"],
                monthly_budget=float(row["monthly_budget"]) if row["monthly_budget"] else None,
                default_model=row["default_model"],
                members=[m["user_id"] for m in members],
                is_active=row["is_active"],
                created_at=row["created_at"],
            ))
        return teams


@router.post("/teams", response_model=Team)
async def create_team(
    team: TeamCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO teams (name, description, monthly_budget, default_model)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, team.name, team.description, team.monthly_budget, team.default_model)

        return Team(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            monthly_budget=float(row["monthly_budget"]) if row["monthly_budget"] else None,
            default_model=row["default_model"],
            members=[],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@router.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    member: TeamMember,
    user: UserInfo = Depends(require_admin)
):
    """Add a member to a team."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO team_members (team_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, user_id) DO UPDATE SET role = $3
        """, team_id, member.user_id, member.role)

    return {"status": "added"}
