"""add reproducible bet-builder quote provenance

Revision ID: c3f91a8d2e40
Revises: b7e31a9d4f62
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3f91a8d2e40"
down_revision: str | Sequence[str] | None = "b7e31a9d4f62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bet_builder_quotes") as batch_op:
        batch_op.add_column(sa.Column("prediction_output_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("feature_version", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("input_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("lower_joint_probability", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("upper_joint_probability", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("independent_product", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dependence_ratio", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("offered_odds_source", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column("offered_odds_observed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("lower_expected_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.create_foreign_key(
            "fk_bet_builder_quotes_prediction_output_id",
            "model_event_outputs",
            ["prediction_output_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint("uq_bet_builder_quotes_fingerprint", ["fingerprint"])
        batch_op.create_check_constraint(
            "ck_bet_builder_quotes_joint_probability",
            "joint_probability >= 0 AND joint_probability <= 1",
        )
        batch_op.create_check_constraint(
            "ck_bet_builder_quotes_lower_probability",
            "lower_joint_probability IS NULL OR "
            "(lower_joint_probability >= 0 AND lower_joint_probability <= joint_probability)",
        )
        batch_op.create_check_constraint(
            "ck_bet_builder_quotes_upper_probability",
            "upper_joint_probability IS NULL OR "
            "(upper_joint_probability >= joint_probability AND upper_joint_probability <= 1)",
        )
        batch_op.create_check_constraint("ck_bet_builder_quotes_fair_odds", "fair_odds >= 1")
        batch_op.create_check_constraint(
            "ck_bet_builder_quotes_offered_odds",
            "offered_odds IS NULL OR offered_odds > 1",
        )
        batch_op.alter_column("warnings", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("bet_builder_quotes") as batch_op:
        batch_op.drop_constraint("ck_bet_builder_quotes_offered_odds", type_="check")
        batch_op.drop_constraint("ck_bet_builder_quotes_fair_odds", type_="check")
        batch_op.drop_constraint("ck_bet_builder_quotes_upper_probability", type_="check")
        batch_op.drop_constraint("ck_bet_builder_quotes_lower_probability", type_="check")
        batch_op.drop_constraint("ck_bet_builder_quotes_joint_probability", type_="check")
        batch_op.drop_constraint("uq_bet_builder_quotes_fingerprint", type_="unique")
        batch_op.drop_constraint("fk_bet_builder_quotes_prediction_output_id", type_="foreignkey")
        batch_op.drop_column("warnings")
        batch_op.drop_column("lower_expected_value")
        batch_op.drop_column("offered_odds_observed_at")
        batch_op.drop_column("offered_odds_source")
        batch_op.drop_column("dependence_ratio")
        batch_op.drop_column("independent_product")
        batch_op.drop_column("upper_joint_probability")
        batch_op.drop_column("lower_joint_probability")
        batch_op.drop_column("input_fingerprint")
        batch_op.drop_column("feature_version")
        batch_op.drop_column("fingerprint")
        batch_op.drop_column("prediction_output_id")
