"""MCP access tokens, rate windows and call records, plus the token lookup function

Record 0006 (tokens) and record 0009 (limits). All three tables are tenant tables: owner_id on
every row, row-level security enabled and forced, the same policy as the collection tables.

A request to a collection's MCP server carries only a token and the collection's public id, so the
owner is not known yet, and forced row-level security would hide the very rows the lookup needs.
`resolve_access_token(token_hash, public_id)` is the one deliberate hole (record 0004): a
SECURITY DEFINER function that returns at most one row (owner, collection, token) and nothing else.
It is owned by `sapiduct_resolver`, a NOLOGIN role that is not the table owner and not BYPASSRLS,
and that has narrow policies of its own: read collections and tokens, and update a token's
last_used_at. (The table owner cannot run it: FORCE makes the owner obey the tenant policy.) The
function pins search_path to the schema followed by pg_temp, qualifies every object, and has
EXECUTE revoked from PUBLIC and granted only to the API role (PostgreSQL docs, CREATE FUNCTION,
"Writing SECURITY DEFINER Functions Safely").

The tables are new, so no existing rows are affected. Downgrading drops them and their rows.

Revision ID: 9d3b6f1e4a72
Revises: 5c1e7a90d2b4
Create Date: 2026-10-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d3b6f1e4a72"
down_revision: str | Sequence[str] | None = "5c1e7a90d2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

API_ROLE = "sapiduct_api"
RESOLVER_ROLE = "sapiduct_resolver"
TENANT_TABLES = ("access_token", "rate_window", "mcp_call")

RESOLVE_FUNCTION = """
CREATE FUNCTION public.resolve_access_token(p_hash bytea, p_public_id text)
RETURNS TABLE (owner_id text, collection_id uuid, token_id uuid)
LANGUAGE sql
VOLATILE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    WITH hit AS (
        SELECT t.id AS token_id, t.owner_id, t.collection_id
        FROM public.access_token t
        JOIN public.collection c ON c.id = t.collection_id AND c.owner_id = t.owner_id
        WHERE t.token_hash = p_hash
          AND c.public_id = p_public_id
          AND t.revoked_at IS NULL
          AND (t.ends_at IS NULL OR t.ends_at > now())
    ), touch AS (
        UPDATE public.access_token t
        SET last_used_at = now()
        FROM hit
        WHERE t.id = hit.token_id
          AND (t.last_used_at IS NULL OR t.last_used_at < now() - interval '1 minute')
    )
    SELECT hit.owner_id, hit.collection_id, hit.token_id FROM hit
$$
"""


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{RESOLVER_ROLE}') THEN
                CREATE ROLE {RESOLVER_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    op.create_table(
        "access_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("last4", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_access_token_hash_is_sha256")
        ),
        sa.ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_access_token_collection_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_access_token_token_hash")),
    )
    op.create_index("ix_access_token_collection", "access_token", ["collection_id"])
    op.create_table(
        "rate_window",
        sa.Column("token_id", sa.Uuid(), nullable=False),
        sa.Column("span", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.CheckConstraint("span IN ('minute', 'day')", name=op.f("ck_rate_window_span")),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["access_token.id"],
            name="fk_rate_window_access_token",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_id", "span", "window_start", name=op.f("pk_rate_window")),
    )
    op.create_index("ix_rate_window_start", "rate_window", ["window_start"])
    op.create_table(
        "mcp_call",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("token_id", sa.Uuid(), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('ok', 'error')", name=op.f("ck_mcp_call_status")),
        sa.ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_mcp_call_collection_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_call")),
    )
    op.create_index(
        "ix_mcp_call_collection_created", "mcp_call", ["collection_id", "created_at", "id"]
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (owner_id = current_setting('app.owner_id', true))
                WITH CHECK (owner_id = current_setting('app.owner_id', true))
            """
        )
    # The API role's privileges on these tables come from the default privileges set in the
    # previous revision. The resolver role gets exactly what the lookup function needs.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {RESOLVER_ROLE}")
    op.execute(f"GRANT SELECT ON collection TO {RESOLVER_ROLE}")
    op.execute(f"GRANT SELECT ON access_token TO {RESOLVER_ROLE}")
    op.execute(f"GRANT UPDATE (last_used_at) ON access_token TO {RESOLVER_ROLE}")
    op.execute(
        f"CREATE POLICY resolver_read ON collection FOR SELECT TO {RESOLVER_ROLE} USING (true)"
    )
    op.execute(
        f"CREATE POLICY resolver_read ON access_token FOR SELECT TO {RESOLVER_ROLE} USING (true)"
    )
    op.execute(
        f"CREATE POLICY resolver_touch ON access_token FOR UPDATE TO {RESOLVER_ROLE} "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(RESOLVE_FUNCTION)
    # Changing a function's owner needs CREATE on its schema for the new owner, only briefly.
    op.execute(f"GRANT CREATE ON SCHEMA public TO {RESOLVER_ROLE}")
    op.execute(f"ALTER FUNCTION public.resolve_access_token(bytea, text) OWNER TO {RESOLVER_ROLE}")
    op.execute(f"REVOKE CREATE ON SCHEMA public FROM {RESOLVER_ROLE}")
    op.execute("REVOKE ALL ON FUNCTION public.resolve_access_token(bytea, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION public.resolve_access_token(bytea, text) TO {API_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.resolve_access_token(bytea, text)")
    op.drop_table("mcp_call")
    op.drop_table("rate_window")
    op.drop_table("access_token")
    op.execute("DROP POLICY IF EXISTS resolver_read ON collection")
    op.execute(f"REVOKE SELECT ON collection FROM {RESOLVER_ROLE}")  # noqa: S608
    # The roles are left in place: other databases on the server may use them.
