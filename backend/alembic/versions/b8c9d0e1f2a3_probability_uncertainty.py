"""persist probability uncertainty provenance

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-30 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "probability_uncertainty",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.drop_column("probability_uncertainty")
