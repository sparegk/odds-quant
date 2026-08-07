from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Sport, Team
from app.db.session import Base
from app.services.team_identity import get_or_create_team


def test_team_identity_only_reconciles_trailing_fc_and_prefers_earliest_id(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/team-identity.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        sport = Sport(slug="football", name="Football")
        session.add(sport)
        session.flush()
        canonical = Team(sport_id=sport.id, name="Manchester City FC")
        duplicate = Team(sport_id=sport.id, name="Manchester City")
        session.add_all([canonical, duplicate])
        session.flush()

        resolved = get_or_create_team(
            session,
            sport_id=sport.id,
            name="Manchester City",
        )
        unrelated = get_or_create_team(session, sport_id=sport.id, name="Manchester")

        assert resolved.id == canonical.id
        assert unrelated.id not in {canonical.id, duplicate.id}
        assert session.scalar(select(Team.name).where(Team.id == unrelated.id)) == "Manchester"
