from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from app.db.session import SessionLocal
from app.schemas.models import EvaluateModelRequest, PredictEventRequest, TrainPoissonRequest
from app.schemas.signals import GenerateSignalsRequest
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.evaluation import EvaluationError, evaluate_model
from app.services.modeling import ModelingError, predict_event, train_poisson_model
from app.services.odds_import import OddsImportError, import_odds_csv
from app.services.results_import import ResultImportError, import_results_csv
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
    train = commands.add_parser("train-poisson", help="train a versioned Poisson baseline")
    train.add_argument("competition_id", type=int)
    train.add_argument("training_start", type=datetime.fromisoformat)
    train.add_argument("training_end", type=datetime.fromisoformat)
    train.add_argument("--minimum-matches", type=int, default=20)
    train.add_argument("--minimum-team-matches", type=int, default=3)
    train.add_argument("--shrinkage-matches", type=float, default=5.0)
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
    except (ModelingError, EvaluationError, SignalGenerationError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}))
        return 2
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
