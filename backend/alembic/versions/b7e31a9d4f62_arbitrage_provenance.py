"""add arbitrage execution provenance

Revision ID: b7e31a9d4f62
Revises: 8d2f6a1c9e04
Create Date: 2026-07-20 03:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e31a9d4f62"
down_revision: str | Sequence[str] | None = "8d2f6a1c9e04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("arbitrage_opportunities") as batch_op:
        batch_op.add_column(sa.Column("fingerprint", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("constraint_status", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("freshness_status", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("budget", sa.Numeric(14, 4), nullable=True))

    op.execute(
        sa.text(
            """UPDATE arbitrage_opportunities
            SET constraint_status = 'unknown',
                freshness_status = 'unknown',
                budget = total_cash_outlay"""
        )
    )

    with op.batch_alter_table("arbitrage_opportunities") as batch_op:
        batch_op.alter_column("constraint_status", nullable=False)
        batch_op.alter_column("freshness_status", nullable=False)
        batch_op.alter_column("budget", nullable=False)
        batch_op.create_unique_constraint("uq_arbitrage_opportunities_fingerprint", ["fingerprint"])
        batch_op.create_check_constraint("ck_arbitrage_opportunities_budget", "budget > 0")

    with op.batch_alter_table("arbitrage_legs") as batch_op:
        batch_op.add_column(sa.Column("bookmaker_constraint_id", sa.Integer()))
        batch_op.add_column(sa.Column("cash_outlay", sa.Numeric(14, 4), nullable=True))
        batch_op.add_column(sa.Column("win_deductions", sa.Numeric(14, 4), nullable=True))

    op.execute(
        sa.text(
            """UPDATE arbitrage_legs
            SET cash_outlay = stake,
                win_deductions = taxes_and_fees"""
        )
    )

    with op.batch_alter_table("arbitrage_legs") as batch_op:
        batch_op.alter_column("cash_outlay", nullable=False)
        batch_op.alter_column("win_deductions", nullable=False)
        batch_op.create_foreign_key(
            "fk_arbitrage_legs_bookmaker_constraint_id",
            "bookmaker_constraints",
            ["bookmaker_constraint_id"],
            ["id"],
        )
        batch_op.create_check_constraint("ck_arbitrage_legs_cash_outlay", "cash_outlay >= stake")
        batch_op.create_check_constraint("ck_arbitrage_legs_win_deductions", "win_deductions >= 0")


def downgrade() -> None:
    with op.batch_alter_table("arbitrage_legs") as batch_op:
        batch_op.drop_constraint("ck_arbitrage_legs_win_deductions", type_="check")
        batch_op.drop_constraint("ck_arbitrage_legs_cash_outlay", type_="check")
        batch_op.drop_constraint("fk_arbitrage_legs_bookmaker_constraint_id", type_="foreignkey")
        batch_op.drop_column("win_deductions")
        batch_op.drop_column("cash_outlay")
        batch_op.drop_column("bookmaker_constraint_id")

    with op.batch_alter_table("arbitrage_opportunities") as batch_op:
        batch_op.drop_constraint("ck_arbitrage_opportunities_budget", type_="check")
        batch_op.drop_constraint("uq_arbitrage_opportunities_fingerprint", type_="unique")
        batch_op.drop_column("budget")
        batch_op.drop_column("freshness_status")
        batch_op.drop_column("constraint_status")
        batch_op.drop_column("fingerprint")
