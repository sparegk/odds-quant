# Recommendation and edge improvements

Each box is implemented, fully verified, committed, and pushed separately. Recommendations remain
conditional decisions from timestamp-valid evidence, never guarantees.

- [x] Require exact fresh quote identity, sourced costs, valid rounded stakes, and positive lower
  net EV before a candidate can appear as an executable recommendation.
- [x] Add an actionable minimum-odds threshold after costs so users can reject a moved price.
- [x] Add a decomposed recommendation-quality score that keeps probability reliability, market
  disagreement, price freshness, and net economics separate.
- [x] Add prospective recommendation tracking with immutable decision-time snapshots and explicit
  closing-line and settlement status.

## Executable recommendation rule

A single-selection recommendation must retain the exact stored VALUE signal snapshot as the current
fresh quote. Its market currency must be known, its tax and stake evidence must pass the existing
source/cutoff/freshness gates, and the reference stake must satisfy minimum, maximum, and increment
rules. Ranking uses lower net EV per cash-outlay unit multiplied by the independently calculated
recommendation-quality score. Missing costs or lower net EV at or below zero suppress the recommendation even
when pre-cost EV is positive.

Builder quotes remain visible for research but cannot be recommendations until their exact quote,
bookmaker identity, currency, settlement, and cost evidence can be joined and validated.

## Minimum acceptable odds

For the displayed valid stake, the app algebraically solves the decimal odds at which expected net
profit using the lower probability bound equals zero. The equation includes stake tax, fixed fee,
winnings tax, payout withholding, and commission. The recommendation card shows this threshold and
instructs the user to reject a moved live price unless it is strictly greater. Equality is break-even,
not positive advantage. The threshold is recalculated from the same sourced terms used by net EV.

## Decomposed recommendation quality

Only signals belonging to the latest cutoff-safe prediction output can become current
recommendations. Each executable candidate exposes five independently inspectable components:
lower-bound interval retention, chronological calibration quality, exact-price freshness,
bookmaker agreement, and lower net economics. Each component is normalized to zero through one,
while raw bookmaker disagreement remains visible beside its normalized component.

The combined quality score is the geometric mean, not an additive points system. A zero component
therefore cannot be hidden by stronger components. Ranking uses lower net EV per cash-outlay unit
multiplied by this decomposed quality score. The score changes ordering only; it does not rewrite
the stored model probability, confidence interval, calibrated VALUE classification, market price,
or realized-return evidence.

## Prospective recommendation tracking

Tracking is explicit so merely viewing research never creates retrospective evidence. Before
kickoff, an administrator captures a currently executable signal with:

```text
POST /api/v1/recommendations/capture
{"signal_id": 123, "captured_at": "2026-08-14T17:55:00Z"}
```

Production requests include `X-Admin-Key`. Capture re-runs the recommendation gates at that exact
cutoff, then fingerprints and stores the signal, exact odds snapshot, model/evaluation provenance,
model input fingerprint, feature version, tax profile, stake-constraint timestamp, market line and
settlement rule, probabilities, after-cost economics, and decomposed quality. The decision row is
one-per-signal, idempotent, and rejects ORM updates.

After kickoff or settlement, refresh the separately stored tracking state with:

```text
POST /api/v1/recommendations/{recommendation_id}/refresh
{"as_of": "2026-08-14T21:00:00Z"}
```

Closing-line status is `PENDING`, `AVAILABLE`, or `UNAVAILABLE`. An available close must be a
complete explicitly closing snapshot for the identical market, selection, bookmaker, and provider;
it must have been observed before kickoff and ingested by the refresh cutoff. Settlement remains
`PENDING` until a final result observed by the cutoff exists, then records the result identity,
settlement, and gross profit units. Later result corrections can update tracking state but cannot
rewrite the immutable decision snapshot. `GET /api/v1/recommendations/tracked` returns the audit
records, and the Value Opportunities screen displays their closing-line and settlement statuses.
