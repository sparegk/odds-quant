"""Retain every confirmed lineup snapshot used by a prediction output."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_output_lineup_snapshots",
        sa.Column("output_id", sa.Integer(), nullable=False),
        sa.Column("lineup_snapshot_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["output_id"], ["model_event_outputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lineup_snapshot_id"], ["lineup_snapshots.id"]),
        sa.PrimaryKeyConstraint("output_id", "lineup_snapshot_id"),
    )


def downgrade() -> None:
    op.drop_table("model_output_lineup_snapshots")
