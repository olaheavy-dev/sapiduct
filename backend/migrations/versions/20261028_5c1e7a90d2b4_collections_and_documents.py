"""Collections and documents, with forced row-level security

The first tenant tables (record 0004). Both carry `owner_id`; a policy lets a row be seen or
written only when its owner is the one the transaction named (`app.owner_id`, set by
app/tenancy.py), and FORCE makes the table's owner obey it too. Superusers and BYPASSRLS roles
still bypass, so the application must connect as `sapiduct_api` (or a role that inherits from it).

`sapiduct_api` is created here as a NOLOGIN group role when it does not exist; the login the
application uses is created by whoever runs the database (the tests create one) and granted it.
Creating a role needs CREATEROLE: a migration role without it fails here, which is the signal to
create the role first. Existing tables get privileges for it too, and tables made later by the
owner role get them by default.

The tables are new, so no existing rows are affected. Downgrading drops them and their rows.

Revision ID: 5c1e7a90d2b4
Revises: app_root
Create Date: 2026-10-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e7a90d2b4"
down_revision: str | Sequence[str] | None = "app_root"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

API_ROLE = "sapiduct_api"
TENANT_TABLES = ("collection", "document")


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{API_ROLE}') THEN
                CREATE ROLE {API_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    op.create_table(
        "collection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), server_default="knowledge", nullable=False),
        sa.Column("public_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('knowledge', 'course')", name=op.f("ck_collection_mode")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection")),
        sa.UniqueConstraint("id", "owner_id", name="uq_collection_id_owner"),
        sa.UniqueConstraint("public_id", name=op.f("uq_collection_public_id")),
    )
    op.create_index(
        "uq_collection_owner_name", "collection", ["owner_id", sa.text("lower(name)")], unique=True
    )
    op.create_table(
        "document",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'parsing', 'indexed', 'failed')", name=op.f("ck_document_status")
        ),
        sa.ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_document_collection_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
    )
    op.create_index(
        "ix_document_collection_created", "document", ["collection_id", "created_at", "id"]
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # current_setting(name, true) is NULL when the setting is missing, so a transaction that
        # never named an owner matches no rows (fails closed).
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (owner_id = current_setting('app.owner_id', true))
                WITH CHECK (owner_id = current_setting('app.owner_id', true))
            """
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {API_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {API_ROLE}")


def downgrade() -> None:
    op.drop_table("document")
    op.drop_table("collection")
    # The role is left in place: other databases on the server may use it.
