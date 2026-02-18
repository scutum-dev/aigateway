"""
Tests for init-db.sql schema validation.

Parses the SQL file textually to verify expected tables, columns, constraints,
indexes, and defaults. Does NOT connect to any database.
"""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
INIT_DB_SQL = ROOT / "init-db.sql"

# Also scan Alembic migration files for tables defined outside init-db.sql.
ALEMBIC_DIR = ROOT / "src" / "admin-api" / "alembic" / "versions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sql_content() -> str:
    """Load the full init-db.sql content once per module."""
    assert INIT_DB_SQL.exists(), f"init-db.sql not found at {INIT_DB_SQL}"
    return INIT_DB_SQL.read_text()


@pytest.fixture(scope="module")
def alembic_sql() -> str:
    """Concatenate all Alembic migration source files into one string."""
    if not ALEMBIC_DIR.is_dir():
        return ""
    parts = []
    for path in sorted(ALEMBIC_DIR.glob("*.py")):
        parts.append(path.read_text())
    return "\n".join(parts)


@pytest.fixture(scope="module")
def combined_sql(sql_content, alembic_sql) -> str:
    """All SQL: init-db.sql + inline SQL in Alembic migration files."""
    return sql_content + "\n" + alembic_sql


def _table_block(combined: str, table_name: str) -> str | None:
    """
    Extract the CREATE TABLE ... (...) block for a given table name.
    Handles nested parentheses (e.g. gen_random_uuid(), UNIQUE(...)).
    Returns the full matched text or None if not found.
    """
    header_pattern = re.compile(
        rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(table_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header_pattern.search(combined)
    if not match:
        return None

    # Walk forward from the opening '(' counting nested parens.
    start = match.start()
    pos = match.end()  # one character after the opening '('
    depth = 1
    while pos < len(combined) and depth > 0:
        ch = combined[pos]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        pos += 1

    return combined[start:pos]


# ===========================================================================
# Table Existence Tests
# ===========================================================================


class TestTableExistence:
    """Verify expected CREATE TABLE statements exist in the combined SQL."""

    # Tables from init-db.sql
    @pytest.mark.parametrize(
        "table_name",
        [
            "budget_alerts",
            "workflow_definitions",
            "workflow_executions",
            "workflow_checkpoints",
            "workflow_steps",
            "mcp_servers",
            "a2a_agents",
            "platform_settings",
            "guardrail_configs",
            "team_guardrails",
            "guardrail_events",
        ],
    )
    def test_init_db_table_exists(self, sql_content, table_name):
        pattern = re.compile(
            rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(table_name)}\b",
            re.IGNORECASE,
        )
        assert pattern.search(sql_content), f"CREATE TABLE {table_name} not found in init-db.sql"

    # Tables from Alembic migrations
    @pytest.mark.parametrize(
        "table_name",
        [
            "model_routing_config",
            "cost_tracking_daily",
            "routing_policies",
            "budgets",
            "teams",
            "team_members",
            "organizations",
            "business_units",
            "sso_configs",
            "audit_logs",
            "rate_limit_policies",
            "model_deprecations",
            "prompt_templates",
            "content_detectors",
        ],
    )
    def test_alembic_table_exists(self, alembic_sql, table_name):
        pattern = re.compile(
            rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(table_name)}\b",
            re.IGNORECASE,
        )
        assert pattern.search(alembic_sql), f"CREATE TABLE {table_name} not found in Alembic migrations"


# ===========================================================================
# UUID Primary Key Tests
# ===========================================================================


class TestUUIDPrimaryKeys:
    """Tables should use UUID primary keys with gen_random_uuid()."""

    @pytest.mark.parametrize(
        "table_name",
        [
            "budget_alerts",
            "workflow_definitions",
            "workflow_executions",
            "workflow_checkpoints",
            "workflow_steps",
            "mcp_servers",
            "a2a_agents",
            "guardrail_configs",
            "team_guardrails",
            "guardrail_events",
        ],
    )
    def test_uuid_pk_with_gen_random_uuid(self, sql_content, table_name):
        block = _table_block(sql_content, table_name)
        assert block is not None, f"Table {table_name} not found"
        assert "gen_random_uuid()" in block.lower(), f"{table_name} does not use gen_random_uuid() for its PK"
        assert "primary key" in block.lower(), f"{table_name} does not declare a PRIMARY KEY"


# ===========================================================================
# Foreign Key Tests
# ===========================================================================


class TestForeignKeys:
    """Verify expected REFERENCES (foreign key) constraints."""

    def test_workflow_executions_references_definitions(self, sql_content):
        block = _table_block(sql_content, "workflow_executions")
        assert block is not None
        assert "references workflow_definitions" in block.lower()

    def test_workflow_checkpoints_references_executions(self, sql_content):
        block = _table_block(sql_content, "workflow_checkpoints")
        assert block is not None
        assert "references workflow_executions" in block.lower()

    def test_workflow_steps_references_executions(self, sql_content):
        block = _table_block(sql_content, "workflow_steps")
        assert block is not None
        assert "references workflow_executions" in block.lower()

    def test_team_guardrails_references_guardrail_configs(self, sql_content):
        block = _table_block(sql_content, "team_guardrails")
        assert block is not None
        assert "references guardrail_configs" in block.lower()

    def test_team_guardrails_has_on_delete_cascade(self, sql_content):
        block = _table_block(sql_content, "team_guardrails")
        assert block is not None
        assert "on delete cascade" in block.lower()

    def test_business_units_references_organizations(self, alembic_sql):
        block = _table_block(alembic_sql, "business_units")
        assert block is not None
        assert "references organizations" in block.lower()

    def test_sso_configs_references_organizations(self, alembic_sql):
        block = _table_block(alembic_sql, "sso_configs")
        assert block is not None
        assert "references organizations" in block.lower()

    def test_org_memberships_references_users(self, alembic_sql):
        block = _table_block(alembic_sql, "org_memberships")
        assert block is not None
        assert "references users" in block.lower()

    def test_team_members_references_teams(self, alembic_sql):
        block = _table_block(alembic_sql, "team_members")
        assert block is not None
        assert "references teams" in block.lower()


# ===========================================================================
# UNIQUE Constraint Tests
# ===========================================================================


class TestUniqueConstraints:
    """Verify that expected UNIQUE constraints are present."""

    def test_workflow_definitions_name_unique(self, sql_content):
        block = _table_block(sql_content, "workflow_definitions")
        assert block is not None
        assert "unique" in block.lower()

    def test_mcp_servers_name_unique(self, sql_content):
        block = _table_block(sql_content, "mcp_servers")
        assert block is not None
        assert "unique" in block.lower()

    def test_a2a_agents_name_unique(self, sql_content):
        block = _table_block(sql_content, "a2a_agents")
        assert block is not None
        assert "unique" in block.lower()

    def test_guardrail_configs_name_unique(self, sql_content):
        block = _table_block(sql_content, "guardrail_configs")
        assert block is not None
        assert "unique" in block.lower()

    def test_team_guardrails_composite_unique(self, sql_content):
        block = _table_block(sql_content, "team_guardrails")
        assert block is not None
        assert "unique(team_id,guardrail_config_id)" in block.lower().replace(" ", "")

    def test_workflow_checkpoints_composite_unique(self, sql_content):
        block = _table_block(sql_content, "workflow_checkpoints")
        assert block is not None
        assert "unique(thread_id,checkpoint_id)" in block.lower().replace(" ", "")

    def test_organizations_name_unique(self, alembic_sql):
        block = _table_block(alembic_sql, "organizations")
        assert block is not None
        assert "unique" in block.lower()

    def test_organizations_slug_unique(self, alembic_sql):
        block = _table_block(alembic_sql, "organizations")
        assert block is not None
        assert "slug" in block.lower()
        # slug should have UNIQUE
        slug_line = [line for line in block.lower().split("\n") if "slug" in line and "unique" in line]
        assert len(slug_line) > 0, "organizations.slug should have UNIQUE constraint"


# ===========================================================================
# DEFAULT Value Tests
# ===========================================================================


class TestDefaultValues:
    """Verify expected DEFAULT values in table definitions."""

    def test_budget_alerts_acknowledged_default_false(self, sql_content):
        block = _table_block(sql_content, "budget_alerts")
        assert block is not None
        assert "default false" in block.lower()

    def test_budget_alerts_created_at_default_timestamp(self, sql_content):
        block = _table_block(sql_content, "budget_alerts")
        assert block is not None
        assert "default current_timestamp" in block.lower()

    def test_workflow_definitions_is_active_default_true(self, sql_content):
        block = _table_block(sql_content, "workflow_definitions")
        assert block is not None
        assert "default true" in block.lower()

    def test_workflow_executions_status_default_pending(self, sql_content):
        block = _table_block(sql_content, "workflow_executions")
        assert block is not None
        assert "default 'pending'" in block.lower()

    def test_mcp_servers_is_active_default_true(self, sql_content):
        block = _table_block(sql_content, "mcp_servers")
        assert block is not None
        assert "default true" in block.lower()

    def test_a2a_agents_is_active_default_true(self, sql_content):
        block = _table_block(sql_content, "a2a_agents")
        assert block is not None
        assert "default true" in block.lower()

    def test_guardrail_configs_mode_default_block(self, sql_content):
        block = _table_block(sql_content, "guardrail_configs")
        assert block is not None
        assert "default 'block'" in block.lower()

    def test_guardrail_events_action_default_blocked(self, sql_content):
        block = _table_block(sql_content, "guardrail_events")
        assert block is not None
        assert "default 'blocked'" in block.lower()


# ===========================================================================
# Index Tests
# ===========================================================================


class TestIndexes:
    """Verify expected CREATE INDEX statements exist."""

    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_budget_alerts_user",
            "idx_budget_alerts_team",
            "idx_budget_alerts_created",
            "idx_executions_user",
            "idx_executions_status",
            "idx_executions_created",
            "idx_checkpoints_thread",
            "idx_steps_execution",
            "idx_team_guardrails_team",
            "idx_guardrail_events_created",
            "idx_guardrail_events_team",
            "idx_guardrail_events_type",
        ],
    )
    def test_index_exists_in_init_db(self, sql_content, index_name):
        pattern = re.compile(
            rf"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(index_name)}\b",
            re.IGNORECASE,
        )
        assert pattern.search(sql_content), f"Index {index_name} not found in init-db.sql"

    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_audit_logs_timestamp",
            "idx_audit_logs_actor_id",
            "idx_audit_logs_org_id",
            "idx_audit_logs_resource",
            "idx_audit_logs_action",
            "idx_rate_limit_events_created",
        ],
    )
    def test_index_exists_in_alembic(self, alembic_sql, index_name):
        pattern = re.compile(
            rf"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(index_name)}\b",
            re.IGNORECASE,
        )
        assert pattern.search(alembic_sql), f"Index {index_name} not found in Alembic migrations"


# ===========================================================================
# Miscellaneous Schema Checks
# ===========================================================================


class TestSchemaExtras:
    """Additional schema integrity checks."""

    def test_uuid_ossp_extension_created(self, sql_content):
        """The uuid-ossp extension should be created."""
        assert "uuid-ossp" in sql_content.lower() or "uuid_ossp" in sql_content.lower()

    def test_litellm_user_created(self, sql_content):
        """A 'litellm' database user should be created."""
        assert re.search(r"CREATE\s+USER\s+litellm", sql_content, re.IGNORECASE)

    def test_litellm_database_created(self, sql_content):
        """A 'litellm' database should be created."""
        assert re.search(r"CREATE\s+DATABASE\s+litellm", sql_content, re.IGNORECASE)

    def test_grant_permissions_to_litellm(self, sql_content):
        """Permissions should be granted to the litellm user."""
        assert "grant" in sql_content.lower() and "litellm" in sql_content.lower()

    def test_platform_settings_has_default_inserts(self, sql_content):
        """platform_settings table should have INSERT statements for defaults."""
        assert "insert into platform_settings" in sql_content.lower()

    def test_guardrail_configs_has_default_insert(self, sql_content):
        """A default guardrail profile should be inserted."""
        assert "insert into guardrail_configs" in sql_content.lower()

    def test_no_drop_table_in_init_sql(self, sql_content):
        """init-db.sql should not contain DROP TABLE statements (additive only)."""
        assert not re.search(r"\bDROP\s+TABLE\b", sql_content, re.IGNORECASE), (
            "init-db.sql should not contain DROP TABLE statements"
        )
