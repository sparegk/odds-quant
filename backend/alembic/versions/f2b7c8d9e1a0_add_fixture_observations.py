"""add fixture observations

Revision ID: f2b7c8d9e1a0
Revises: c3f91a8d2e40
Create Date: 2026-07-23 01:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b7c8d9e1a0"
down_revision: str | None = "c3f91a8d2e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fixture_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.CheckConstraint("ingested_at >= observed_at"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "provider_id", "observed_at"),
    )
    op.create_index(
        op.f("ix_fixture_observations_observed_at"),
        "fixture_observations",
        ["observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_fixture_observations_observed_at"),
        table_name="fixture_observations",
    )
    op.drop_table("fixture_observations")
