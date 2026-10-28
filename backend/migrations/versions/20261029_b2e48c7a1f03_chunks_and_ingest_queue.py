"""Chunks, the ingestion queue, and the function a worker claims a job with

Record 0008. `chunk` and `ingest_job` are tenant tables: owner_id on every row, row-level security
enabled and forced, the same policy as the other tenant tables, and a composite foreign key to the
document so the database refuses a chunk or job whose collection or owner does not match.
`document` gains the stored file's key, the generation counters search reads, and `indexed_at`.

A worker serves every owner, so it cannot name one before it has a job, and forced row-level
security would hide the queue from it. `claim_ingest_job(lease_seconds)` is the one deliberate
hole, built like the token lookup (record 0004): a SECURITY DEFINER function owned by
`sapiduct_queue`, a NOLOGIN role that is neither the table owner nor BYPASSRLS and whose policies
reach only the queue table. It takes the next due job with FOR UPDATE SKIP LOCKED, marks it running
with a lease, and returns who the job is for; from there the worker names the owner and every
query goes through the ordinary policies. EXECUTE goes only to `sapiduct_worker`, a role that also
has everything the API role has. (Narrowing the worker further waits for its own container.)

Existing documents get generation 0 (nothing published) and no stored key. The new tables are
empty. Downgrading drops them and the new columns.

Revision ID: b2e48c7a1f03
Revises: 9d3b6f1e4a72
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2e48c7a1f03"
down_revision: str | Sequence[str] | None = "9d3b6f1e4a72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

API_ROLE = "sapiduct_api"
WORKER_ROLE = "sapiduct_worker"
QUEUE_ROLE = "sapiduct_queue"
TENANT_TABLES = ("chunk", "ingest_job")

CLAIM_FUNCTION = """
CREATE FUNCTION public.claim_ingest_job(p_lease_seconds integer)
RETURNS TABLE (job_id uuid, owner_id text, document_id uuid, collection_id uuid, attempts integer)
LANGUAGE sql
VOLATILE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    WITH next AS (
        SELECT j.id
        FROM public.ingest_job j
        WHERE (j.status = 'queued' AND j.run_after <= now())
           OR (j.status = 'running' AND j.locked_until < now())
        ORDER BY j.run_after, j.id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE public.ingest_job j
    SET status = 'running',
        attempts = j.attempts + 1,
        locked_until = now() + make_interval(secs => p_lease_seconds)
    FROM next
    WHERE j.id = next.id
    RETURNING j.id, j.owner_id, j.document_id, j.collection_id, j.attempts
$$
"""


def _create_role(name: str, member_of: str | None = None) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{name}') THEN
                CREATE ROLE {name} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    if member_of:
        op.execute(f"GRANT {member_of} TO {name}")


def upgrade() -> None:
    _create_role(QUEUE_ROLE)
    _create_role(WORKER_ROLE, member_of=API_ROLE)
    op.add_column("document", sa.Column("object_key", sa.Text(), nullable=True))
    op.add_column(
        "document", sa.Column("generation", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "document",
        sa.Column("published_generation", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("document", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_document_id_collection_owner", "document", ["id", "collection_id", "owner_id"]
    )
    op.create_table(
        "chunk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "collection_id", "owner_id"],
            ["document.id", "document.collection_id", "document.owner_id"],
            name="fk_chunk_document",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
        sa.UniqueConstraint("document_id", "generation", "position", name="uq_chunk_position"),
    )
    op.create_index("ix_chunk_collection", "chunk", ["collection_id"])
    op.create_table(
        "ingest_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name=op.f("ck_ingest_job_status")
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "collection_id", "owner_id"],
            ["document.id", "document.collection_id", "document.owner_id"],
            name="fk_ingest_job_document",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingest_job")),
    )
    op.create_index(
        "uq_ingest_job_live",
        "ingest_job",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "ix_ingest_job_due",
        "ingest_job",
        ["run_after"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
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
    # The API role's privileges on the new tables come from the default privileges set earlier.
    # The queue role reaches only the queue table, and only to claim a job.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {QUEUE_ROLE}")
    op.execute(f"GRANT SELECT, UPDATE ON ingest_job TO {QUEUE_ROLE}")
    op.execute(
        f"CREATE POLICY queue_claim ON ingest_job TO {QUEUE_ROLE} USING (true) WITH CHECK (true)"
    )
    op.execute(CLAIM_FUNCTION)
    op.execute(f"GRANT CREATE ON SCHEMA public TO {QUEUE_ROLE}")
    op.execute(f"ALTER FUNCTION public.claim_ingest_job(integer) OWNER TO {QUEUE_ROLE}")
    op.execute(f"REVOKE CREATE ON SCHEMA public FROM {QUEUE_ROLE}")
    op.execute("REVOKE ALL ON FUNCTION public.claim_ingest_job(integer) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION public.claim_ingest_job(integer) TO {WORKER_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.claim_ingest_job(integer)")
    op.drop_table("ingest_job")
    op.drop_table("chunk")
    op.drop_constraint("uq_document_id_collection_owner", "document", type_="unique")
    for column in ("indexed_at", "published_generation", "generation", "object_key"):
        op.drop_column("document", column)
    # The roles are left in place: other databases on the server may use them.
