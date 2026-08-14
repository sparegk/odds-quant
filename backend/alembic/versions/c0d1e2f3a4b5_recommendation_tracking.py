"""add prospective recommendation tracking

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-08-14 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: str | Sequence[str] | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("selection_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("odds_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_run_id", sa.Integer(), nullable=False),
        sa.Column("tax_profile_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tax_profile_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("constraint_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_type", sa.String(length=40), nullable=False),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("selection_code", sa.String(length=40), nullable=False),
        sa.Column("settlement_rule_key", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("offered_odds", sa.Float(), nullable=False),
        sa.Column("model_probability", sa.Float(), nullable=False),
        sa.Column("lower_probability", sa.Float(), nullable=False),
        sa.Column("lower_expected_value", sa.Float(), nullable=False),
        sa.Column("net_expected_value", sa.Float(), nullable=False),
        sa.Column("lower_net_expected_value", sa.Float(), nullable=False),
        sa.Column("stake", sa.Float(), nullable=False),
        sa.Column("cash_outlay", sa.Float(), nullable=False),
        sa.Column("minimum_acceptable_odds", sa.Float(), nullable=False),
        sa.Column("recommendation_quality", sa.JSON(), nullable=False),
        sa.Column("model_input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=80), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint("captured_at < kickoff_at"),
        sa.CheckConstraint("price_observed_at <= captured_at"),
        sa.CheckConstraint("offered_odds > 1 AND minimum_acceptable_odds > 1"),
        sa.CheckConstraint("lower_net_expected_value > 0"),
        sa.CheckConstraint("stake > 0 AND cash_outlay > 0"),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["backtest_runs.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"]),
        sa.ForeignKeyConstraint(["odds_snapshot_id"], ["odds_snapshots.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["model_predictions.id"]),
        sa.ForeignKeyConstraint(["selection_id"], ["selections.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["value_signals.id"]),
        sa.ForeignKeyConstraint(["tax_profile_id"], ["tax_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
        sa.UniqueConstraint("signal_id"),
    )
    op.create_index(
        op.f("ix_recommendation_snapshots_captured_at"),
        "recommendation_snapshots",
        ["captured_at"],
        unique=False,
    )
    op.create_table(
        "recommendation_tracking_states",
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("closing_line_status", sa.String(length=20), nullable=False),
        sa.Column("closing_odds_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("closing_odds", sa.Float(), nullable=True),
        sa.Column("closing_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_line_value", sa.Float(), nullable=True),
        sa.Column("settlement_status", sa.String(length=20), nullable=False),
        sa.Column("result_id", sa.Integer(), nullable=True),
        sa.Column("settlement", sa.String(length=20), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profit_units", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("closing_line_status IN ('PENDING', 'AVAILABLE', 'UNAVAILABLE')"),
        sa.CheckConstraint("settlement_status IN ('PENDING', 'SETTLED')"),
        sa.ForeignKeyConstraint(["closing_odds_snapshot_id"], ["odds_snapshots.id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendation_snapshots.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["result_id"], ["match_results.id"]),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )


def downgrade() -> None:
    op.drop_table("recommendation_tracking_states")
    op.drop_index(
        op.f("ix_recommendation_snapshots_captured_at"),
        table_name="recommendation_snapshots",
    )
    op.drop_table("recommendation_snapshots")
