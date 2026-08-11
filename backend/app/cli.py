from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.api_football import ApiFootballClient, ApiFootballError
from app.providers.odds_api_io import OddsApiIoClient, OddsApiIoError
from app.providers.openfootball import (
    OPENFOOTBALL_CHAMPIONS_LICENSE_URL,
    OPENFOOTBALL_EUROPE_LICENSE_URL,
    OPENFOOTBALL_LICENSE_URL,
    OpenFootballImportError,
    normalize_openfootball_results,
    normalize_openfootball_text_results,
)
from app.schemas.api import CollectionMonitoringView
from app.schemas.models import (
    EvaluateModelRequest,
    PredictEventRequest,
    TrainEloRequest,
    TrainPoissonRequest,
)
from app.schemas.signals import GenerateSignalsRequest
from app.services.api_football_collection import collect_api_football_intelligence
from app.services.collection_monitoring import collection_monitoring
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.evaluation import EvaluationError, evaluate_model
from app.services.market_edge_coverage import market_edge_coverage
from app.services.modeling import (
    ModelingError,
    activate_cold_start_model,
    predict_event,
    train_elo_model,
    train_poisson_model,
)
from app.services.odds_import import OddsImportError, import_odds_csv
from app.services.results_import import (
    ResultImportError,
    import_results_csv,
    serialize_result_rows_csv,
)
from app.services.signals import SignalGenerationError, generate_value_signals


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oddsquant")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed-demo", help="load labelled synthetic football odds")
    seed.add_argument("--as-of", type=datetime.fromisoformat)
    seed_results = commands.add_parser(
        "seed-demo-results", help="load labelled synthetic historical football results"
    )
    seed_results.add_argument("--as-of", type=datetime.fromisoformat)
    import_command = commands.add_parser("import-odds", help="import a validated odds CSV")
    import_command.add_argument("path", type=Path)
    results_command = commands.add_parser(
        "import-results", help="import validated historical football results"
    )
    results_command.add_argument("path", type=Path)
    openfootball = commands.add_parser(
        "import-openfootball-results",
        help="normalize and import a pinned CC0 OpenFootball JSON dataset",
    )
    openfootball.add_argument("path", type=Path)
    openfootball.add_argument("--dataset-path", required=True)
    openfootball.add_argument("--competition", required=True)
    openfootball.add_argument("--country", required=True)
    openfootball.add_argument("--season", required=True)
    openfootball.add_argument("--timezone", required=True)
    openfootball.add_argument("--source-commit", required=True)
    openfootball.add_argument("--source-updated-at", required=True, type=datetime.fromisoformat)
    openfootball_text = commands.add_parser(
        "import-openfootball-text-results",
        help="normalize and import a pinned CC0 OpenFootball Football.TXT dataset",
    )
    openfootball_text.add_argument("path", type=Path)
    openfootball_text.add_argument("--dataset-path", required=True)
    openfootball_text.add_argument("--competition", required=True)
    openfootball_text.add_argument("--country", required=True)
    openfootball_text.add_argument("--season", required=True)
    openfootball_text.add_argument("--timezone", required=True)
    openfootball_text.add_argument("--source-commit", required=True)
    openfootball_text.add_argument(
        "--source-updated-at", required=True, type=datetime.fromisoformat
    )
    openfootball_text.add_argument("--team-aliases", type=Path)
    openfootball_text.add_argument(
        "--repository",
        choices=("champions-league", "europe"),
        default="champions-league",
    )
    commands.add_parser(
        "probe-target-bookmakers",
        help="verify configured odds-provider coverage for required bookmakers",
    )
    commands.add_parser(
        "probe-bet-builder-markets",
        help="report sanitized corner/shot/player market metadata without ingesting props",
    )
    api_football = commands.add_parser(
        "collect-api-football-intelligence",
        help="collect exact-match lineups, injuries, and completed player statistics",
    )
    api_football.add_argument("--date", type=date.fromisoformat, default=date.today())
    monitor = commands.add_parser(
        "monitor-collection",
        help="report persisted provider-job health and permitted data coverage",
    )
    monitor.add_argument("--recent-job-limit", type=int, default=10)
    monitor.add_argument(
        "--fail-on-alerts",
        action="store_true",
        help="exit with status 3 when collection alerts are present",
    )
    commands.add_parser(
        "audit-market-edge-coverage",
        help="report outcome-blind coverage for the frozen market-edge cohort",
    )
    train = commands.add_parser("train-poisson", help="train a versioned Poisson baseline")
    train.add_argument("competition_id", type=int)
    train.add_argument("training_start", type=datetime.fromisoformat)
    train.add_argument("training_end", type=datetime.fromisoformat)
    train.add_argument("--minimum-matches", type=int, default=20)
    train.add_argument("--minimum-team-matches", type=int, default=3)
    train.add_argument("--shrinkage-matches", type=float, default=5.0)
    activate_cold_start = commands.add_parser(
        "activate-cold-start",
        help="create the receipt-bound probability-only cold-start model path",
    )
    activate_cold_start.add_argument("source_model_id", type=int)
    train_elo = commands.add_parser(
        "train-elo", help="register a versioned Davidson Elo research candidate"
    )
    train_elo.add_argument("competition_id", type=int)
    train_elo.add_argument("training_start", type=datetime.fromisoformat)
    train_elo.add_argument("training_end", type=datetime.fromisoformat)
    train_elo.add_argument("--minimum-matches", type=int, default=20)
    train_elo.add_argument("--minimum-team-matches", type=int, default=3)
    train_elo.add_argument("--initial-rating", type=float, default=1500.0)
    train_elo.add_argument("--k-factor", type=float, default=20.0)
    train_elo.add_argument("--scale", type=float, default=400.0)
    train_elo.add_argument("--home-advantage", type=float, default=75.0)
    train_elo.add_argument("--draw-probability-at-even-strength", type=float, default=0.26)
    predict = commands.add_parser("predict-event", help="store a pre-kickoff model prediction")
    predict.add_argument("model_id", type=int)
    predict.add_argument("event_id", type=int)
    predict.add_argument("--predicted-at", type=datetime.fromisoformat)
    predict.add_argument("--inputs-as-of", type=datetime.fromisoformat)
    evaluate = commands.add_parser(
        "evaluate-model", help="run an expanding-window chronological evaluation"
    )
    evaluate.add_argument("model_id", type=int)
    evaluate.add_argument("evaluation_start", type=datetime.fromisoformat)
    evaluate.add_argument("evaluation_end", type=datetime.fromisoformat)
    evaluate.add_argument("--prediction-lead-minutes", type=int, default=60)
    evaluate.add_argument("--minimum-training-matches", type=int, default=20)
    evaluate.add_argument("--calibration-bins", type=int, default=10)
    evaluate.add_argument("--include-cold-start-benchmark", action="store_true")
    evaluate.add_argument("--include-cold-start-validation", action="store_true")
    signals = commands.add_parser(
        "generate-signals", help="join a calibrated prediction to compatible fresh odds"
    )
    signals.add_argument("output_id", type=int)
    signals.add_argument("--generated-at", type=datetime.fromisoformat)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        with SessionLocal() as session:
            result: BaseModel
            if args.command == "seed-demo":
                result = seed_demo_data(session, as_of=args.as_of)
            elif args.command == "seed-demo-results":
                result = seed_demo_results(session, as_of=args.as_of)
            elif args.command == "import-odds":
                path: Path = args.path
                result = import_odds_csv(
                    session,
                    filename=path.name,
                    content=path.read_bytes(),
                )
            elif args.command == "import-results":
                path = args.path
                result = import_results_csv(
                    session,
                    filename=path.name,
                    content=path.read_bytes(),
                )
            elif args.command == "import-openfootball-results":
                path = args.path
                rows = normalize_openfootball_results(
                    path.read_bytes(),
                    dataset_path=args.dataset_path,
                    competition=args.competition,
                    country=args.country,
                    season=args.season,
                    timezone=args.timezone,
                    source_commit=args.source_commit,
                    source_updated_at=args.source_updated_at,
                )
                result = import_results_csv(
                    session,
                    filename=f"openfootball-{args.season}-{args.source_commit[:12]}.csv",
                    content=serialize_result_rows_csv(rows),
                    provider_slug="openfootball-cc0",
                    provider_name="OpenFootball CC0 results",
                    provider_kind="open_data",
                    provider_terms_url=OPENFOOTBALL_LICENSE_URL,
                )
            elif args.command == "import-openfootball-text-results":
                path = args.path
                aliases: dict[str, str] = {}
                if args.team_aliases is not None:
                    raw_aliases = json.loads(args.team_aliases.read_text(encoding="utf-8"))
                    if not isinstance(raw_aliases, dict) or any(
                        not isinstance(key, str) or not isinstance(value, str)
                        for key, value in raw_aliases.items()
                    ):
                        raise OpenFootballImportError(
                            "team aliases file must be a JSON object of string names"
                        )
                    aliases = raw_aliases
                rows = normalize_openfootball_text_results(
                    path.read_bytes(),
                    dataset_path=args.dataset_path,
                    competition=args.competition,
                    country=args.country,
                    season=args.season,
                    timezone=args.timezone,
                    source_commit=args.source_commit,
                    source_updated_at=args.source_updated_at,
                    team_aliases=aliases,
                )
                result = import_results_csv(
                    session,
                    filename=f"openfootball-champions-{args.season}-{args.source_commit[:12]}.csv",
                    content=serialize_result_rows_csv(rows),
                    provider_slug=(
                        "openfootball-champions-cc0"
                        if args.repository == "champions-league"
                        else "openfootball-europe-cc0"
                    ),
                    provider_name=(
                        "OpenFootball Champions League CC0 results"
                        if args.repository == "champions-league"
                        else "OpenFootball Europe CC0 results"
                    ),
                    provider_kind="open_data",
                    provider_terms_url=(
                        OPENFOOTBALL_CHAMPIONS_LICENSE_URL
                        if args.repository == "champions-league"
                        else OPENFOOTBALL_EUROPE_LICENSE_URL
                    ),
                )
            elif args.command == "probe-target-bookmakers":
                settings = get_settings()
                with OddsApiIoClient(
                    settings.odds_api_io_key or "",
                    base_url=settings.odds_api_io_base_url,
                ) as client:
                    result = client.probe_target_bookmakers()
            elif args.command == "probe-bet-builder-markets":
                settings = get_settings()
                with OddsApiIoClient(
                    settings.odds_api_io_key or "",
                    base_url=settings.odds_api_io_base_url,
                ) as client:
                    result = client.probe_bet_builder_markets(observed_at=datetime.now(UTC))
            elif args.command == "collect-api-football-intelligence":
                settings = get_settings()
                with ApiFootballClient(
                    settings.api_football_key or "",
                    base_url=settings.api_football_base_url,
                    daily_request_reserve=settings.api_football_daily_request_reserve,
                ) as client:
                    account = client.account_probe()
                    if not account.active:
                        raise ApiFootballError("API-Football account is inactive")
                    coverage = client.target_coverage().leagues
                    result = collect_api_football_intelligence(
                        session,
                        client=client,
                        coverage=coverage,
                        on_date=args.date,
                    )
            elif args.command == "monitor-collection":
                settings = get_settings()
                result = collection_monitoring(
                    session,
                    expected_poll_seconds=settings.provider_poll_seconds,
                    recent_job_limit=args.recent_job_limit,
                )
            elif args.command == "audit-market-edge-coverage":
                result = market_edge_coverage(session)
            elif args.command == "train-poisson":
                result = train_poisson_model(
                    session,
                    TrainPoissonRequest(
                        competition_id=args.competition_id,
                        training_start=args.training_start,
                        training_end=args.training_end,
                        minimum_matches=args.minimum_matches,
                        minimum_team_matches=args.minimum_team_matches,
                        shrinkage_matches=args.shrinkage_matches,
                    ),
                )
            elif args.command == "train-elo":
                result = train_elo_model(
                    session,
                    TrainEloRequest(
                        competition_id=args.competition_id,
                        training_start=args.training_start,
                        training_end=args.training_end,
                        minimum_matches=args.minimum_matches,
                        minimum_team_matches=args.minimum_team_matches,
                        initial_rating=args.initial_rating,
                        k_factor=args.k_factor,
                        scale=args.scale,
                        home_advantage=args.home_advantage,
                        draw_probability_at_even_strength=(args.draw_probability_at_even_strength),
                    ),
                )
            elif args.command == "activate-cold-start":
                result = activate_cold_start_model(session, args.source_model_id)
            elif args.command == "predict-event":
                result = predict_event(
                    session,
                    args.model_id,
                    PredictEventRequest(
                        event_id=args.event_id,
                        predicted_at=args.predicted_at,
                        inputs_as_of=args.inputs_as_of,
                    ),
                )
            elif args.command == "evaluate-model":
                result = evaluate_model(
                    session,
                    args.model_id,
                    EvaluateModelRequest(
                        evaluation_start=args.evaluation_start,
                        evaluation_end=args.evaluation_end,
                        prediction_lead_minutes=args.prediction_lead_minutes,
                        minimum_training_matches=args.minimum_training_matches,
                        calibration_bins=args.calibration_bins,
                        include_cold_start_benchmark=args.include_cold_start_benchmark,
                        include_cold_start_validation=args.include_cold_start_validation,
                    ),
                )
            else:
                result = generate_value_signals(
                    session,
                    GenerateSignalsRequest(
                        output_id=args.output_id,
                        generated_at=args.generated_at,
                    ),
                )
    except (OddsImportError, ResultImportError) as exc:
        print(json.dumps({"status": "rejected", "job_id": exc.job_id, "errors": exc.errors}))
        return 2
    except OpenFootballImportError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}))
        return 2
    except OddsApiIoError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}))
        return 2
    except ApiFootballError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}))
        return 2
    except (ModelingError, EvaluationError, SignalGenerationError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}))
        return 2
    print(result.model_dump_json())
    if isinstance(result, CollectionMonitoringView) and args.fail_on_alerts and result.alerts:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
