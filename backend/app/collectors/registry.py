from __future__ import annotations

from app.providers.base import SUPPORTED_PROVIDER_KINDS, OddsProvider

_odds_providers: dict[str, OddsProvider] = {}


def register_odds_provider(provider: OddsProvider) -> None:
    if provider.kind not in SUPPORTED_PROVIDER_KINDS:
        raise ValueError(f"unsupported provider kind {provider.kind!r}")
    if provider.kind not in {"licensed_api", "official_source", "demo_seed"}:
        raise ValueError("scheduled adapters must be licensed, official, or explicitly demo")
    if provider.kind in {"licensed_api", "official_source"} and not provider.terms_url:
        raise ValueError("external scheduled adapters require a terms or source URL")
    if provider.slug in _odds_providers:
        raise ValueError(f"odds provider {provider.slug!r} is already registered")
    _odds_providers[provider.slug] = provider


def registered_odds_providers() -> tuple[OddsProvider, ...]:
    return tuple(_odds_providers.values())


def clear_provider_registry() -> None:
    """Clear process-local adapters; intended for deterministic tests."""
    _odds_providers.clear()
