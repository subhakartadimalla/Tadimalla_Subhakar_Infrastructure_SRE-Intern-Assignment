"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("component_id", sa.String(length=128), nullable=False),
        sa.Column("component_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("status", sa.Enum("OPEN", "INVESTIGATING", "RESOLVED", "CLOSED", name="incident_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_incidents_component_id", "incidents", ["component_id"])

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("component_id", sa.String(length=128), nullable=False),
        sa.Column("component_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_signals_component_id", "signals", ["component_id"])

    op.create_table(
        "rcas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("root_cause_category", sa.String(length=64), nullable=False),
        sa.Column("fix_applied", sa.Text(), nullable=False),
        sa.Column("prevention_steps", sa.Text(), nullable=False),
        sa.Column("mttr_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rcas")
    op.drop_index("ix_signals_component_id", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_incidents_component_id", table_name="incidents")
    op.drop_table("incidents")
    op.execute("DROP TYPE IF EXISTS incident_status")

