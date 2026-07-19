from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.db.session import SessionLocal
from app.services.demo_seed import seed_demo_data
from app.services.odds_import import OddsImportError, import_odds_csv


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oddsquant")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed-demo", help="load labelled synthetic football odds")
    seed.add_argument("--as-of", type=datetime.fromisoformat)
    import_command = commands.add_parser("import-odds", help="import a validated odds CSV")
    import_command.add_argument("path", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        with SessionLocal() as session:
            if args.command == "seed-demo":
                result = seed_demo_data(session, as_of=args.as_of)
            else:
                path: Path = args.path
                result = import_odds_csv(
                    session,
                    filename=path.name,
                    content=path.read_bytes(),
                )
    except OddsImportError as exc:
        print(json.dumps({"status": "rejected", "job_id": exc.job_id, "errors": exc.errors}))
        return 2
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
