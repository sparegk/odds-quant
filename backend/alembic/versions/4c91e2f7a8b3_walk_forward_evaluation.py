"""add immutable walk-forward evaluation evidence

Revision ID: 4c91e2f7a8b3
Revises: e7a4c0d1b292
Create Date: 2026-07-20 02:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4c91e2f7a8b3"
down_revision: str | Sequence[str] | None = "e7a4c0d1b292"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch_op:
        batch_op.add_column(sa.Column("fingerprint", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("policy", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.add_column(
            sa.Column(
                "evaluation_status",
                sa.String(30),
                nullable=False,
                server_default="unvalidated",
            )
        )
        batch_op.create_unique_constraint("uq_backtest_runs_fingerprint", ["fingerprint"])
        batch_op.create_check_constraint(
            "ck_backtest_runs_train_validation_window", "validation_end >= train_end"
        )
        batch_op.create_check_constraint(
            "ck_backtest_runs_validation_test_window", "test_end >= validation_end"
        )
        batch_op.alter_column("policy", server_default=None)
        batch_op.alter_column("evaluation_status", server_default=None)

    with op.batch_alter_table("backtest_observations") as batch_op:
        batch_op.alter_column("selection_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("odds_snapshot_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("prediction_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("result_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("training_cutoff", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("training_sample_size", sa.Integer()))
        batch_op.add_column(sa.Column("training_fingerprint", sa.String(64)))
        batch_op.add_column(sa.Column("market_type", sa.String(40)))
        batch_op.add_column(sa.Column("probabilities", sa.JSON()))
        batch_op.add_column(sa.Column("actual_outcome", sa.String(40)))
        batch_op.add_column(sa.Column("brier_score", sa.Float()))
        batch_op.add_column(sa.Column("log_loss", sa.Float()))
        batch_op.add_column(
            sa.Column("market_snapshot_ids", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("market_probabilities", sa.JSON()))
        batch_op.add_column(sa.Column("market_brier_score", sa.Float()))
        batch_op.add_column(sa.Column("market_log_loss", sa.Float()))
        batch_op.create_foreign_key(
            "fk_backtest_observations_result_id", "match_results", ["result_id"], ["id"]
        )
        batch_op.create_check_constraint(
            "ck_backtest_observations_training_sample",
            "training_sample_size IS NULL OR training_sample_size > 0",
        )
        batch_op.create_check_constraint(
            "ck_backtest_observations_training_cutoff",
            "training_cutoff IS NULL OR training_cutoff <= predicted_at",
        )
        batch_op.create_check_constraint(
            "ck_backtest_observations_brier", "brier_score IS NULL OR brier_score >= 0"
        )
        batch_op.create_check_constraint(
            "ck_backtest_observations_log_loss", "log_loss IS NULL OR log_loss >= 0"
        )
        batch_op.alter_column("market_snapshot_ids", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("backtest_observations") as batch_op:
        batch_op.drop_constraint("ck_backtest_observations_log_loss", type_="check")
        batch_op.drop_constraint("ck_backtest_observations_brier", type_="check")
        batch_op.drop_constraint("ck_backtest_observations_training_cutoff", type_="check")
        batch_op.drop_constraint("ck_backtest_observations_training_sample", type_="check")
        batch_op.drop_constraint("fk_backtest_observations_result_id", type_="foreignkey")
        for column in (
            "market_log_loss",
            "market_brier_score",
            "market_probabilities",
            "market_snapshot_ids",
            "log_loss",
            "brier_score",
            "actual_outcome",
            "probabilities",
            "market_type",
            "training_fingerprint",
            "training_sample_size",
            "training_cutoff",
            "result_id",
        ):
            batch_op.drop_column(column)
        batch_op.alter_column("prediction_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("odds_snapshot_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("selection_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("backtest_runs") as batch_op:
        batch_op.drop_constraint("ck_backtest_runs_validation_test_window", type_="check")
        batch_op.drop_constraint("ck_backtest_runs_train_validation_window", type_="check")
        batch_op.drop_constraint("uq_backtest_runs_fingerprint", type_="unique")
        batch_op.drop_column("evaluation_status")
        batch_op.drop_column("policy")
        batch_op.drop_column("fingerprint")
