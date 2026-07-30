from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestResult,
    BacktestRun,
    Competition,
    Event,
    LineupMember,
    LineupSnapshot,
    MatchResult,
    ModelEventOutput,
    ModelOutputLineupSnapshot,
    ModelPrediction,
    ModelVersion,
    Player,
    Provider,
)
from app.db.session import Base
from app.quant.poisson import derive_market
from app.schemas.models import PredictEventRequest, TrainEloRequest, TrainPoissonRequest
from app.services.demo_seed import build_demo_results_csv, seed_demo_data, seed_demo_results
from app.services.modeling import (
    ELO_MODEL_KIND,
    ModelingError,
    predict_event,
    train_elo_model,
    train_poisson_model,
)
from app.services.results_import import import_results_csv

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/modeling.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _training_request(session: Session) -> TrainPoissonRequest:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    return TrainPoissonRequest(
        competition_id=competition_id,
        training_start=AS_OF - timedelta(days=150),
        training_end=AS_OF,
        minimum_matches=20,
        minimum_team_matches=3,
        shrinkage_matches=5,
    )


def _elo_training_request(session: Session) -> TrainEloRequest:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    return TrainEloRequest(
        competition_id=competition_id,
        training_start=AS_OF - timedelta(days=150),
        training_end=AS_OF,
        minimum_matches=20,
        minimum_team_matches=3,
    )


def _store_confirmed_lineups(session: Session, event: Event, published_at: datetime) -> list[int]:
    competition = session.get_one(Competition, event.competition_id)
    provider = Provider(
        slug="confirmed-lineup-test",
        name="Confirmed lineup test",
        kind="licensed_api",
        is_demo=False,
        terms_url="https://example.test/terms",
        capabilities={"lineups": True},
    )
    session.add(provider)
    session.flush()
    ids: list[int] = []
    for team_index, team_id in enumerate((event.home_team_id, event.away_team_id)):
        lineup = LineupSnapshot(
            event_id=event.id,
            team_id=team_id,
            coach_id=None,
            provider_id=provider.id,
            lineup_type="confirmed",
            formation="4-3-3",
            source_updated_at=published_at,
            observed_at=published_at,
            confidence=1,
        )
        session.add(lineup)
        session.flush()
        ids.append(lineup.id)
        for player_index in range(11):
            player = Player(
                sport_id=competition.sport_id,
                provider_id=provider.id,
                provider_player_key=f"{team_index}-{player_index}",
                name=f"Player {team_index}-{player_index}",
                position="unknown",
                preferred_side=None,
                birth_year=None,
                is_demo=False,
            )
            session.add(player)
            session.flush()
            session.add(
                LineupMember(
                    lineup_snapshot_id=lineup.id,
                    player_id=player.id,
                    starter=True,
                    position="unknown",
                    role=None,
                    expected_probability=None,
                )
            )
    session.commit()
    return ids


def test_training_and_prediction_are_versioned_and_persisted(session: Session) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None

    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )
    repeated = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )

    assert model.sample_size == 32
    assert model.evaluation_status == "unvalidated"
    assert model.metrics["held_out_evaluation"] is False
    assert output.id == repeated.id
    assert output.home_lambda > 0 and output.away_lambda > 0
    assert sum(output.derived_probabilities["MATCH_RESULT"].values()) == pytest.approx(1)
    assert sum(output.derived_probabilities["TOTAL_GOALS_2.5"].values()) == pytest.approx(1)
    assert len(output.predictions) == 3
    assert output.probability_uncertainty.method == ("chronological_moving_block_bootstrap_refit")
    assert output.probability_uncertainty.version == "probability-uncertainty-v1"
    assert output.probability_uncertainty.successful_refits == 400
    assert output.probability_uncertainty.block_length == 6
    assert output.probability_uncertainty.training_fingerprint == model.data_fingerprint
    assert output.probability_calibration.applied is False
    assert all(
        prediction.lower_probability <= prediction.probability <= prediction.upper_probability
        for prediction in output.predictions
    )
    assert session.scalar(select(func.count()).select_from(ModelPrediction)) == 3


def test_elo_candidate_training_is_versioned_deterministic_and_unvalidated(
    session: Session,
) -> None:
    request = _elo_training_request(session)

    original = train_elo_model(session, request, now=AS_OF)
    repeated = train_elo_model(session, request, now=AS_OF + timedelta(hours=1))

    assert repeated.id == original.id
    assert original.kind == ELO_MODEL_KIND
    assert original.version.startswith("elo1-")
    assert original.sample_size == 32
    assert original.probability_evaluation_status == "unvalidated"
    assert original.evaluation_status == "unvalidated"
    assert original.metrics == {
        "metric_scope": "training_descriptive_only",
        "held_out_evaluation": False,
        "teams": 8,
        "outcome_counts": {"HOME": 16, "DRAW": 8, "AWAY": 8},
    }
    assert original.config["algorithm_version"] == "davidson-elo-v1"
    assert original.config["results_ordering"] == "observed_at_then_event_id"
    assert original.config["initial_rating"] == 1500.0
    assert original.config["k_factor"] == 20.0
    assert original.config["scale"] == 400.0
    assert original.config["home_advantage"] == 75.0
    assert original.config["draw_probability_at_even_strength"] == 0.26
    assert session.scalar(select(func.count()).select_from(ModelEventOutput)) == 0


def test_post_cutoff_correction_cannot_change_elo_candidate_training(
    session: Session,
) -> None:
    request = _elo_training_request(session)
    original = train_elo_model(session, request, now=AS_OF)
    result = session.scalar(select(MatchResult).order_by(MatchResult.id))
    assert result is not None
    session.add(
        MatchResult(
            event_id=result.event_id,
            provider_id=result.provider_id,
            home_goals=result.home_goals + 5,
            away_goals=result.away_goals,
            status="final",
            is_final=True,
            source_updated_at=AS_OF + timedelta(hours=1),
            observed_at=AS_OF + timedelta(hours=1),
            settled_at=AS_OF + timedelta(hours=1),
            supersedes_id=result.id,
        )
    )
    session.commit()

    repeated = train_elo_model(session, request, now=AS_OF + timedelta(hours=2))

    assert repeated.id == original.id
    assert repeated.data_fingerprint == original.data_fingerprint
    assert repeated.sample_size == 32


def test_prediction_applies_only_an_accepted_pre_cutoff_calibrator(
    session: Session,
) -> None:
    model_view = train_poisson_model(session, _training_request(session), now=AS_OF)
    model = session.get_one(ModelVersion, model_view.id)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None
    model.is_demo = False
    target.is_demo = False
    run = BacktestRun(
        model_version_id=model.id,
        status="completed",
        train_end=AS_OF - timedelta(days=3),
        validation_end=AS_OF - timedelta(days=2),
        test_end=AS_OF - timedelta(days=1),
        fingerprint="accepted-temperature-calibration-run",
        config={"evaluation_kind": "expanding_window_match_result"},
        policy={
            "version": "separated-probability-market-v5",
            "probability_decision": "probability_validated",
            "market_decision": "insufficient_market_evidence",
            "probability_checks": {"chronological_recalibration_accepted": True},
        },
        probability_evaluation_status="probability_validated",
        evaluation_status="insufficient_market_evidence",
        is_demo=False,
    )
    session.add(run)
    session.flush()
    session.add(
        BacktestResult(
            run_id=run.id,
            benchmark="temperature_scaled",
            dimension="overall",
            dimension_value="all",
            metrics={
                "activation_status": "accepted",
                "final_calibrator": {
                    "version": "walk-forward-temperature-scaling-v1",
                    "temperature": 2.0,
                    "sample_size": 240,
                    "input_fingerprint": "a" * 64,
                    "fit_through": (AS_OF - timedelta(days=1)).isoformat(),
                    "accepted": True,
                },
            },
        )
    )
    session.commit()

    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )

    raw = derive_market(np.asarray(output.score_matrix), "MATCH_RESULT")
    calibrated = output.derived_probabilities["MATCH_RESULT"]
    assert output.probability_calibration.applied is True
    assert output.probability_calibration.temperature == pytest.approx(2.0)
    assert output.probability_calibration.evaluation_run_id == run.id
    assert calibrated["HOME"] != pytest.approx(raw["HOME"])
    assert sum(calibrated.values()) == pytest.approx(1)
    assert {item.selection_code: item.probability for item in output.predictions} == pytest.approx(
        calibrated
    )


def test_confirmed_lineups_create_a_separate_unadjusted_context_version(
    session: Session,
) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None
    baseline = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )
    target.is_demo = False
    session.get_one(ModelVersion, model.id).is_demo = False
    session.commit()
    confirmed_at = AS_OF
    lineup_ids = _store_confirmed_lineups(session, target, confirmed_at)

    confirmed = predict_event(
        session,
        model.id,
        PredictEventRequest(
            event_id=target.id,
            predicted_at=confirmed_at,
            inputs_as_of=confirmed_at,
        ),
        now=confirmed_at,
        lineup_snapshot_ids=lineup_ids,
    )
    repeated = predict_event(
        session,
        model.id,
        PredictEventRequest(
            event_id=target.id,
            predicted_at=confirmed_at,
            inputs_as_of=confirmed_at,
        ),
        now=confirmed_at,
        lineup_snapshot_ids=lineup_ids,
    )

    assert baseline.evidence_class == "team_baseline"
    assert baseline.lineup_snapshot_ids == []
    assert confirmed.evidence_class == "confirmed_lineup_context_unadjusted"
    assert confirmed.lineup_snapshot_ids == sorted(lineup_ids)
    assert repeated.id == confirmed.id
    assert confirmed.home_lambda == baseline.home_lambda
    assert confirmed.away_lambda == baseline.away_lambda
    assert session.scalar(select(func.count()).select_from(ModelOutputLineupSnapshot)) == 2
    assert session.scalar(select(func.count()).select_from(ModelEventOutput)) == 2


def test_post_cutoff_correction_cannot_change_training_data(session: Session) -> None:
    request = _training_request(session)
    original = train_poisson_model(session, request, now=AS_OF)
    result = session.scalar(select(MatchResult).order_by(MatchResult.id))
    assert result is not None
    session.add(
        MatchResult(
            event_id=result.event_id,
            provider_id=result.provider_id,
            home_goals=result.home_goals + 5,
            away_goals=result.away_goals,
            status="final",
            is_final=True,
            source_updated_at=AS_OF + timedelta(hours=1),
            observed_at=AS_OF + timedelta(hours=1),
            settled_at=result.settled_at,
            supersedes_id=result.id,
        )
    )
    session.commit()

    repeated = train_poisson_model(session, request, now=AS_OF + timedelta(hours=2))

    assert repeated.id == original.id
    assert repeated.data_fingerprint == original.data_fingerprint
    assert repeated.sample_size == 32


def test_confirmed_lineup_published_after_cutoff_cannot_enter_prediction(
    session: Session,
) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None
    target.is_demo = False
    session.get_one(ModelVersion, model.id).is_demo = False
    session.commit()
    lineup_ids = _store_confirmed_lineups(session, target, AS_OF + timedelta(seconds=1))

    with pytest.raises(ModelingError, match="before cutoff"):
        predict_event(
            session,
            model.id,
            PredictEventRequest(
                event_id=target.id,
                predicted_at=AS_OF,
                inputs_as_of=AS_OF,
            ),
            now=AS_OF,
            lineup_snapshot_ids=lineup_ids,
        )


def test_prediction_at_or_after_kickoff_is_rejected(session: Session) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None

    with pytest.raises(ModelingError, match="before kickoff"):
        predict_event(
            session,
            model.id,
            PredictEventRequest(
                event_id=target.id,
                predicted_at=target.kickoff_at.replace(tzinfo=UTC),
                inputs_as_of=AS_OF,
            ),
        )


def test_duplicate_result_provider_does_not_double_count_matches(session: Session) -> None:
    import_results_csv(
        session,
        filename="second-provider.csv",
        content=build_demo_results_csv(AS_OF),
        provider_slug="second-results-provider",
        provider_name="Second synthetic result source",
        is_demo=True,
        now=AS_OF,
    )

    model = train_poisson_model(session, _training_request(session), now=AS_OF)

    assert model.sample_size == 32


def test_current_season_model_uses_only_same_canonical_competition_history(
    session: Session,
) -> None:
    prior_season = session.scalar(select(Competition))
    assert prior_season is not None
    current_season = Competition(
        sport_id=prior_season.sport_id,
        name=prior_season.name,
        country=prior_season.country,
        season="2027/2028",
    )
    session.add(current_season)
    session.flush()
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None
    target.competition_id = current_season.id
    session.commit()

    request = _training_request(session).model_copy(update={"competition_id": current_season.id})
    model = train_poisson_model(session, request, now=AS_OF)
    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )

    assert model.sample_size == 32
    assert model.feature_version == "final-score-home-away-v3-bootstrap-uncertainty"
    assert model.config["competition_id"] == current_season.id
    assert model.config["training_competition_ids"] == [
        prior_season.id,
        current_season.id,
    ]
    assert model.config["training_competition_scope"] == ("same_sport_name_country_all_seasons")
    assert output.event_id == target.id
