"""add calibrated value signal provenance

Revision ID: 8d2f6a1c9e04
Revises: 4c91e2f7a8b3
Create Date: 2026-07-20 03:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d2f6a1c9e04"
down_revision: str | Sequence[str] | None = "4c91e2f7a8b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("value_signals") as batch_op:
        batch_op.add_column(sa.Column("evaluation_run_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("lower_expected_value", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("calibration_error", sa.Float(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("odds_age_minutes", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("bookmaker_count", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("odds_move_ratio", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("implied_move_points", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.create_foreign_key(
            "fk_value_signals_evaluation_run_id",
            "backtest_runs",
            ["evaluation_run_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_value_signals_snapshot_prediction_generated",
            ["odds_snapshot_id", "prediction_id", "generated_at"],
        )
        batch_op.create_check_constraint("ck_value_signals_odds", "offered_odds > 1")
        batch_op.create_check_constraint(
            "ck_value_signals_probability_bounds",
            "raw_implied_probability > 0 AND raw_implied_probability < 1 "
            "AND market_fair_probability > 0 AND market_fair_probability < 1 "
            "AND model_probability >= 0 AND model_probability <= 1 "
            "AND confidence >= 0 AND confidence <= 1",
        )
        batch_op.create_check_constraint(
            "ck_value_signals_reliability",
            "calibration_error >= 0 AND odds_age_minutes >= 0 AND bookmaker_count > 0",
        )
        batch_op.alter_column("lower_expected_value", server_default=None)
        batch_op.alter_column("calibration_error", server_default=None)
        batch_op.alter_column("odds_age_minutes", server_default=None)
        batch_op.alter_column("bookmaker_count", server_default=None)
        batch_op.alter_column("odds_move_ratio", server_default=None)
        batch_op.alter_column("implied_move_points", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("value_signals") as batch_op:
        batch_op.drop_constraint("ck_value_signals_reliability", type_="check")
        batch_op.drop_constraint("ck_value_signals_probability_bounds", type_="check")
        batch_op.drop_constraint("ck_value_signals_odds", type_="check")
        batch_op.drop_constraint("uq_value_signals_snapshot_prediction_generated", type_="unique")
        batch_op.drop_constraint("fk_value_signals_evaluation_run_id", type_="foreignkey")
        for column in (
            "implied_move_points",
            "odds_move_ratio",
            "bookmaker_count",
            "odds_age_minutes",
            "calibration_error",
            "lower_expected_value",
            "evaluation_run_id",
        ):
            batch_op.drop_column(column)
