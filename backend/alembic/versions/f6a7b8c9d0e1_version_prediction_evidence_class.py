"""Allow baseline and confirmed-context outputs at the same cutoff."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_COLUMNS = ["event_id", "model_version_id", "predicted_at"]
_NEW_COLUMNS = [*_OLD_COLUMNS, "evidence_class"]
_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _constraint_name(columns: list[str]) -> str | None:
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("model_event_outputs")
    target = set(columns)
    for constraint in constraints:
        if set(constraint.get("column_names") or []) == target:
            name = constraint.get("name")
            return str(name) if name else None
    return None


def upgrade() -> None:
    old_name = _constraint_name(_OLD_COLUMNS) or "uq_model_event_outputs_event_id"
    with op.batch_alter_table(
        "model_event_outputs", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint(old_name, type_="unique")
        batch.create_unique_constraint(
            "uq_model_event_outputs_event_model_time_evidence", _NEW_COLUMNS
        )


def downgrade() -> None:
    new_name = _constraint_name(_NEW_COLUMNS) or "uq_model_event_outputs_event_model_time_evidence"
    with op.batch_alter_table(
        "model_event_outputs", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint(new_name, type_="unique")
        batch.create_unique_constraint("uq_model_event_outputs_event_id", _OLD_COLUMNS)
