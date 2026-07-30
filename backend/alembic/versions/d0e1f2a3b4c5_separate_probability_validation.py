"""separate probability and market validation provenance

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-30 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "probability_evaluation_status",
                sa.String(length=40),
                nullable=False,
                server_default="unvalidated",
            )
        )
    with op.batch_alter_table("backtest_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "probability_evaluation_status",
                sa.String(length=40),
                nullable=False,
                server_default="unvalidated",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch_op:
        batch_op.drop_column("probability_evaluation_status")
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.drop_column("probability_evaluation_status")
