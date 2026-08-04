"""persist fail-closed feature activation evidence

Revision ID: b9c0d1e2f3a4
Revises: e1f2a3b4c5d6
Create Date: 2026-08-04 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9c0d1e2f3a4"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "feature_activation",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.drop_column("feature_activation")
