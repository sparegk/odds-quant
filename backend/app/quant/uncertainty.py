from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np

from app.quant.team_strength import HistoricalScore, fit_poisson_team_strength


@dataclass(frozen=True)
class BootstrapExpectedGoals:
    samples: list[tuple[float, float]]
    block_length: int
    requested_refits: int
    attempted_refits: int
    seed_fingerprint: str


def chronological_block_bootstrap_expected_goals(
    matches: list[HistoricalScore],
    *,
    home_team_id: int,
    away_team_id: int,
    shrinkage_matches: float,
    resamples: int,
    seed_material: str,
    block_length: int | None = None,
) -> BootstrapExpectedGoals:
    """Refit team strengths on circular blocks from an ordered training history."""

    if len(matches) < 4:
        raise ValueError("block bootstrap requires at least four chronological matches")
    if home_team_id == away_team_id:
        raise ValueError("bootstrap forecast requires two different teams")
    if resamples < 100:
        raise ValueError("block bootstrap requires at least 100 refits")
    if not seed_material:
        raise ValueError("block bootstrap seed material is required")
    resolved_block_length = block_length or max(2, round(math.sqrt(len(matches))))
    if not 1 <= resolved_block_length <= len(matches):
        raise ValueError("block length must be between 1 and the training sample size")

    seed_digest = hashlib.sha256(seed_material.encode()).digest()
    generator = np.random.default_rng(int.from_bytes(seed_digest[:8], "big"))
    samples: list[tuple[float, float]] = []
    attempts = 0
    maximum_attempts = resamples * 10
    while len(samples) < resamples and attempts < maximum_attempts:
        attempts += 1
        sampled = _circular_block_sample(
            matches,
            block_length=resolved_block_length,
            generator=generator,
        )
        try:
            fitted = fit_poisson_team_strength(
                sampled,
                shrinkage_matches=shrinkage_matches,
            )
            samples.append(fitted.expected_goals(home_team_id, away_team_id))
        except ValueError:
            continue
    if len(samples) != resamples:
        raise ValueError(
            f"only {len(samples)} of {resamples} bootstrap refits retained both target teams"
        )
    return BootstrapExpectedGoals(
        samples=samples,
        block_length=resolved_block_length,
        requested_refits=resamples,
        attempted_refits=attempts,
        seed_fingerprint=hashlib.sha256(seed_material.encode()).hexdigest(),
    )


def bootstrap_probability_interval(
    point_probability: float,
    sampled_probabilities: list[float],
    *,
    confidence_level: float,
) -> tuple[float, float]:
    if not math.isfinite(point_probability) or not 0 <= point_probability <= 1:
        raise ValueError("point probability must be finite and in [0, 1]")
    if len(sampled_probabilities) < 100:
        raise ValueError("probability interval requires at least 100 bootstrap samples")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence level must be in (0, 1)")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in sampled_probabilities):
        raise ValueError("bootstrap probabilities must be finite and in [0, 1]")
    tail = (1.0 - confidence_level) / 2.0
    lower, upper = np.quantile(sampled_probabilities, [tail, 1.0 - tail]).tolist()
    return (min(float(lower), point_probability), max(float(upper), point_probability))


def _circular_block_sample(
    matches: list[HistoricalScore],
    *,
    block_length: int,
    generator: np.random.Generator,
) -> list[HistoricalScore]:
    sampled: list[HistoricalScore] = []
    while len(sampled) < len(matches):
        start = int(generator.integers(0, len(matches)))
        sampled.extend(matches[(start + offset) % len(matches)] for offset in range(block_length))
    return sampled[: len(matches)]
