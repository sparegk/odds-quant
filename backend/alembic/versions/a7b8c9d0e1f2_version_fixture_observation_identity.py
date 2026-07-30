"""version fixture observation identity

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-30 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fixture_observations", sa.Column("competition_id", sa.Integer()))
    op.add_column("fixture_observations", sa.Column("home_team_id", sa.Integer()))
    op.add_column("fixture_observations", sa.Column("away_team_id", sa.Integer()))
    op.add_column("fixture_observations", sa.Column("kickoff_at", sa.DateTime(timezone=True)))
    op.execute(
        sa.text(
            """
            UPDATE fixture_observations
            SET competition_id = (
                    SELECT events.competition_id FROM events
                    WHERE events.id = fixture_observations.event_id
                ),
                home_team_id = (
                    SELECT events.home_team_id FROM events
                    WHERE events.id = fixture_observations.event_id
                ),
                away_team_id = (
                    SELECT events.away_team_id FROM events
                    WHERE events.id = fixture_observations.event_id
                ),
                kickoff_at = (
                    SELECT events.kickoff_at FROM events
                    WHERE events.id = fixture_observations.event_id
                )
            """
        )
    )
    with op.batch_alter_table("fixture_observations", recreate="always") as batch:
        batch.alter_column("competition_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("home_team_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("away_team_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("kickoff_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_foreign_key(
            "fk_fixture_observations_competition_id", "competitions", ["competition_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_fixture_observations_home_team_id", "teams", ["home_team_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_fixture_observations_away_team_id", "teams", ["away_team_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_fixture_observations_distinct_teams", "home_team_id <> away_team_id"
        )


def downgrade() -> None:
    with op.batch_alter_table("fixture_observations", recreate="always") as batch:
        batch.drop_constraint("ck_fixture_observations_distinct_teams", type_="check")
        batch.drop_constraint("fk_fixture_observations_away_team_id", type_="foreignkey")
        batch.drop_constraint("fk_fixture_observations_home_team_id", type_="foreignkey")
        batch.drop_constraint("fk_fixture_observations_competition_id", type_="foreignkey")
        batch.drop_column("kickoff_at")
        batch.drop_column("away_team_id")
        batch.drop_column("home_team_id")
        batch.drop_column("competition_id")
