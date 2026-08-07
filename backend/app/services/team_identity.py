from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Team


def get_or_create_team(session: Session, *, sport_id: int, name: str) -> Team:
    """Resolve the narrow provider variation `Club` versus `Club FC`."""
    variants = _trailing_fc_variants(name)
    existing = session.scalar(
        select(Team).where(Team.sport_id == sport_id, Team.name.in_(variants)).order_by(Team.id)
    )
    if existing is not None:
        return existing
    team = Team(sport_id=sport_id, name=name)
    session.add(team)
    session.flush()
    return team


def _trailing_fc_variants(name: str) -> tuple[str, ...]:
    if name.casefold().endswith(" fc"):
        return (name[:-3], name)
    return (name, f"{name} FC")
