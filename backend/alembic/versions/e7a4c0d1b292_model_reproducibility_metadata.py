"""add model reproducibility metadata and quantitative constraints

Revision ID: e7a4c0d1b292
Revises: 60f015680124
Create Date: 2026-07-19 16:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7a4c0d1b292"
down_revision: str | Sequence[str] | None = "60f015680124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.add_column(
            sa.Column("data_fingerprint", sa.String(length=64), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "feature_version",
                sa.String(length=60),
                nullable=False,
                server_default="goals-v1",
            )
        )
        batch_op.add_column(
            sa.Column("sample_size", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "evaluation_status",
                sa.String(length=30),
                nullable=False,
                server_default="unvalidated",
            )
        )
        batch_op.create_check_constraint(
            "ck_model_versions_training_window", "training_end > training_start"
        )
        batch_op.create_check_constraint("ck_model_versions_sample_size", "sample_size > 0")
        batch_op.alter_column("data_fingerprint", server_default=None)
        batch_op.alter_column("feature_version", server_default=None)
        batch_op.alter_column("sample_size", server_default=None)
        batch_op.alter_column("evaluation_status", server_default=None)

    with op.batch_alter_table("match_results") as batch_op:
        batch_op.create_check_constraint(
            "ck_match_results_nonnegative_goals", "home_goals >= 0 AND away_goals >= 0"
        )
        batch_op.create_check_constraint(
            "ck_match_results_settlement_observation", "settled_at <= observed_at"
        )

    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.create_check_constraint(
            "ck_model_outputs_input_chronology", "inputs_as_of <= predicted_at"
        )
        batch_op.create_check_constraint(
            "ck_model_outputs_positive_lambdas", "home_lambda > 0 AND away_lambda > 0"
        )
        batch_op.create_check_constraint("ck_model_outputs_sample_size", "sample_size > 0")

    with op.batch_alter_table("model_predictions") as batch_op:
        batch_op.create_check_constraint(
            "ck_model_predictions_probability_bounds",
            "probability >= 0 AND probability <= 1 "
            "AND lower_probability >= 0 AND lower_probability <= probability "
            "AND upper_probability >= probability AND upper_probability <= 1",
        )
        batch_op.create_check_constraint("ck_model_predictions_fair_odds", "fair_odds >= 1")


def downgrade() -> None:
    with op.batch_alter_table("model_predictions") as batch_op:
        batch_op.drop_constraint("ck_model_predictions_fair_odds", type_="check")
        batch_op.drop_constraint("ck_model_predictions_probability_bounds", type_="check")

    with op.batch_alter_table("model_event_outputs") as batch_op:
        batch_op.drop_constraint("ck_model_outputs_sample_size", type_="check")
        batch_op.drop_constraint("ck_model_outputs_positive_lambdas", type_="check")
        batch_op.drop_constraint("ck_model_outputs_input_chronology", type_="check")

    with op.batch_alter_table("match_results") as batch_op:
        batch_op.drop_constraint("ck_match_results_settlement_observation", type_="check")
        batch_op.drop_constraint("ck_match_results_nonnegative_goals", type_="check")

    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.drop_constraint("ck_model_versions_sample_size", type_="check")
        batch_op.drop_constraint("ck_model_versions_training_window", type_="check")
        batch_op.drop_column("evaluation_status")
        batch_op.drop_column("sample_size")
        batch_op.drop_column("feature_version")
        batch_op.drop_column("data_fingerprint")
