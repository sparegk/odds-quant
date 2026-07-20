from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalInput:
    offered_odds: float
    market_probability: float
    model_probability: float
    lower_probability: float
    sample_size_per_team: int
    calibration_error: float
    age_minutes: float
    bookmaker_count: int
    odds_move_ratio: float = 0.0
    implied_move_points: float = 0.0

    def __post_init__(self) -> None:
        if not 1 < self.offered_odds < 1001:
            raise ValueError("offered_odds must be greater than 1 and below 1001")
        for name, probability in (
            ("market_probability", self.market_probability),
            ("model_probability", self.model_probability),
            ("lower_probability", self.lower_probability),
        ):
            if not 0 <= probability <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.lower_probability > self.model_probability:
            raise ValueError("lower_probability cannot exceed model_probability")
        if self.sample_size_per_team < 0 or self.bookmaker_count < 0:
            raise ValueError("sample and bookmaker counts cannot be negative")
        if (
            self.calibration_error < 0
            or self.age_minutes < 0
            or self.odds_move_ratio < 0
            or self.implied_move_points < 0
        ):
            raise ValueError("reliability and movement inputs cannot be negative")


def confidence_score(value: SignalInput) -> float:
    sample = min(value.sample_size_per_team / 20.0, 1.0)
    calibration = max(0.0, 1.0 - value.calibration_error / 0.15)
    freshness = max(0.0, 1.0 - value.age_minutes / 60.0)
    coverage = min(value.bookmaker_count / 3.0, 1.0)
    return 0.4 * sample + 0.3 * calibration + 0.2 * freshness + 0.1 * coverage


def classify_signal(value: SignalInput) -> dict[str, object]:
    ev = value.model_probability * value.offered_odds - 1.0
    lower_ev = value.lower_probability * value.offered_odds - 1.0
    edge = value.model_probability - value.market_probability
    confidence = confidence_score(value)
    reasons = [f"Model probability differs from market consensus by {edge:+.1%}."]
    risks: list[str] = []
    inadequate = (
        value.sample_size_per_team < 8
        or value.calibration_error > 0.10
        or value.age_minutes > 60
        or value.bookmaker_count < 1
    )
    moved = value.odds_move_ratio >= 0.10 or value.implied_move_points >= 0.05
    if value.age_minutes > 15:
        risks.append("Odds snapshot is aging and may no longer be available.")
    if moved:
        risks.append("The market moved materially after the previous snapshot.")
    if lower_ev <= 0:
        risks.append("The lower uncertainty bound does not retain positive EV.")
    if inadequate:
        signal = "INSUFFICIENT_DATA"
        risks.append("Reliability gates for sample size, calibration, or freshness failed.")
    elif ev >= 0.05 and edge >= 0.03 and confidence >= 0.65 and lower_ev > 0 and not moved:
        signal = "VALUE"
        reasons.append("EV, edge, confidence, and uncertainty gates all pass.")
    elif value.offered_odds < 2 and edge <= -0.03 and ev <= -0.05:
        signal = "OVERPRICED_FAVORITE"
        reasons.append("The favourite price implies materially more confidence than the model.")
    elif ev > 0 or edge > 0:
        signal = "WATCH"
    else:
        signal = "PASS"
    return {
        "signal": signal,
        "expected_value": ev,
        "lower_expected_value": lower_ev,
        "edge": edge,
        "confidence": confidence,
        "reasons": reasons,
        "risks": risks,
    }
