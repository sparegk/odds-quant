from pathlib import Path

from app.core.config import Settings


def test_shared_env_ignores_frontend_settings(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ODDSQUANT_ODDS_API_IO_KEY=test-provider-key\nVITE_API_BASE_URL=http://127.0.0.1:8000\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.odds_api_io_key == "test-provider-key"
