"""work items + rca

Revision ID: 0002_work_items_rca
Revises: 0001_init
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0002_work_items_rca"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bootstrap safety: earlier iterations of this repo created a legacy `rcas` table.
    # To keep `alembic upgrade head` runnable in fresh and existing dev DBs, drop it.
    op.execute("DROP TABLE IF EXISTS rcas CASCADE")

    op.create_table(
        "work_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("component_id", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.Enum("P0", "P1", "P2", name="severity_level"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "INVESTIGATING", "RESOLVED", "CLOSED", name="work_item_status"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("first_signal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_signal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_work_items_component_id", "work_items", ["component_id"])
    op.create_index("ix_work_items_status", "work_items", ["status"])
    op.create_index("ix_work_items_severity", "work_items", ["severity"])
    op.create_index("ix_work_items_component_id_created_at", "work_items", ["component_id", "created_at"])

    op.create_table(
        "rcas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "work_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("fix_applied", sa.Text(), nullable=False),
        sa.Column("prevention_steps", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mttr", sa.Float(), nullable=False),
    )
    op.create_index("ix_rcas_work_item_id", "rcas", ["work_item_id"])


def downgrade() -> None:
    op.drop_index("ix_rcas_work_item_id", table_name="rcas")
    op.drop_table("rcas")
    op.drop_index("ix_work_items_component_id_created_at", table_name="work_items")
    op.drop_index("ix_work_items_severity", table_name="work_items")
    op.drop_index("ix_work_items_status", table_name="work_items")
    op.drop_index("ix_work_items_component_id", table_name="work_items")
    op.drop_table("work_items")
    op.execute("DROP TYPE IF EXISTS work_item_status")
    op.execute("DROP TYPE IF EXISTS severity_level")

