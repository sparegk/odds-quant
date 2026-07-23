"""canonicalize target competition identities

Revision ID: a13c7e9b4d20
Revises: f2b7c8d9e1a0
Create Date: 2026-07-23 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a13c7e9b4d20"
down_revision: str | None = "f2b7c8d9e1a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALIASES = (
    ("England - Premier League", "Premier League", "England", "2026/27"),
    (
        "International Clubs - UEFA Champions League",
        "UEFA Champions League",
        "International",
        "2026/27",
    ),
    (
        "International Clubs - UEFA Champions League, Qualification",
        "UEFA Champions League Qualification",
        "International",
        "2026/27",
    ),
    (
        "International Clubs - UEFA Conference League",
        "UEFA Conference League",
        "International",
        "2026/27",
    ),
    (
        "International Clubs - UEFA Conference League, Qualification",
        "UEFA Conference League Qualification",
        "International",
        "2026/27",
    ),
)


def upgrade() -> None:
    _rename_competitions(forward=True)


def downgrade() -> None:
    _rename_competitions(forward=False)


def _rename_competitions(*, forward: bool) -> None:
    competitions = sa.table(
        "competitions",
        sa.column("id", sa.Integer),
        sa.column("sport_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("country", sa.String),
        sa.column("season", sa.String),
    )
    connection = op.get_bind()
    for alias, canonical, country, season in _ALIASES:
        source_name, target_name = (alias, canonical) if forward else (canonical, alias)
        source_rows = connection.execute(
            sa.select(competitions.c.id, competitions.c.sport_id).where(
                competitions.c.name == source_name,
                competitions.c.country == country,
                competitions.c.season == season,
            )
        ).all()
        for source_id, sport_id in source_rows:
            conflict = connection.scalar(
                sa.select(competitions.c.id).where(
                    competitions.c.sport_id == sport_id,
                    competitions.c.name == target_name,
                    competitions.c.season == season,
                    competitions.c.id != source_id,
                )
            )
            if conflict is not None:
                raise RuntimeError(
                    f"cannot rename competition {source_name!r}: {target_name!r} already exists"
                )
            connection.execute(
                sa.update(competitions)
                .where(competitions.c.id == source_id)
                .values(name=target_name)
            )
