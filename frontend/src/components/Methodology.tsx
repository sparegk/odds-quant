import { AlertTriangle } from 'lucide-react'

export function Methodology() {
  const methods = [
    ['Market probability', 'Decimal prices are converted to raw implied probabilities. Complete markets are de-vigged with proportional and power methods; overlapping outcomes are never treated as independent.'],
    ['Model probability', 'Independent football models must use only evidence available before kickoff, preserve model versions, and report uncertainty rather than copying bookmaker probabilities.'],
    ['Signals', 'Model edge, line-shopping improvement, and bookmaker margin remain separate. Stale data, weak calibration, missing inputs, or uncertainty wider than the edge block a strong signal.'],
    ['Historical evaluation', 'Training and evaluation use chronological cutoffs and walk-forward tests. Final lineups, corrected results, and closing prices cannot leak into earlier predictions.'],
    ['Arbitrage', 'Only mutually exclusive and exhaustive outcomes with identical settlement rules can be combined. Taxes, fees, stake limits, rounding, void risk, and price movement must be included.'],
    ['Live collection', 'Registered providers poll only at the configured cadence. Every accepted record retains source and observation timestamps; protected services and inferred closing flags remain prohibited.'],
    ['Prediction skips', 'Upcoming prediction refreshes fail closed with a bounded reason vocabulary. Insufficient home or away venue history is reported as monitoring evidence and never bypassed by lowering the minimum history gate.'],
    ['Lineup evidence', 'Team-baseline predictions remain separate from confirmed-lineup context. Confirmed snapshots may be attached only with original publication timestamps; probabilities remain unadjusted until player-strength effects pass independent chronological validation.'],
    ['Model promotion', 'Promotion requires permitted non-demo history, complete chronological replay coverage, calibrated status, and paired proper-score evidence against the fixed uniform benchmark. Training fit and demo evaluations cannot promote a model.'],
    ['Closing prices', 'CLV uses only explicit source-timestamped closing snapshots for the same market, bookmaker, provider, selection, period, line, and settlement rule. The latest observed price is never inferred to be closing.'],
  ]
  const lifecycle = [
    ['1', 'Ingest', 'Atomic timestamped fixtures, results, odds, and intelligence.', 'Reject incomplete identity, chronology, or settlement evidence.'],
    ['2', 'Predict', 'Persist a pre-kickoff model output with exact cutoff and fingerprint.', 'Skip when model or venue-specific history is insufficient.'],
    ['3', 'Evaluate', 'Replay expanding chronological windows and compare proper scores.', 'Block promotion without non-demo calibration and benchmark evidence.'],
    ['4', 'Classify', 'Generate signals only from compatible fresh prices and stored predictions.', 'Keep model edge, margin, and line shopping separate.'],
    ['5', 'Review', 'Backtest settled signals, explicit CLV, and constrained bankroll paths.', 'Treat every result as research evidence, never a profit guarantee.'],
  ]
  return <div className="max-w-5xl"><SectionHeading eyebrow="Statistical integrity" title="Research methodology" /><div className="border-y border-zinc-200 bg-white">{methods.map(([title, detail]) => <div key={title} className="grid grid-cols-[190px_1fr] gap-2 border-b border-zinc-100 px-5 py-5 last:border-0"><h3 className="font-semibold">{title}</h3><p className="text-sm leading-6 text-zinc-600">{detail}</p></div>)}</div><MethodologyLifecycle lifecycle={lifecycle} /><div className="mt-5 flex gap-3 border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-950"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={19} /><p>No prediction guarantees profit. Odds and statistical relationships change, historical performance does not ensure future performance, and this project is not affiliated with any bookmaker.</p></div></div>
}

function MethodologyLifecycle({ lifecycle }: { lifecycle: string[][] }) { return <section className="mt-7" aria-label="Operational evidence lifecycle"><SectionHeading eyebrow="Point-in-time controls" title="Operational evidence lifecycle" /><div className="overflow-x-auto border-y border-zinc-200 bg-white"><table className="w-full min-w-[820px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Step</th><th className="px-4 py-3">Layer</th><th className="px-4 py-3">Stored evidence</th><th className="px-4 py-3">Fail-closed boundary</th></tr></thead><tbody>{lifecycle.map(([step, layer, evidence, boundary]) => <tr className="border-t border-zinc-100 align-top" key={step}><td className="px-4 py-3 font-mono font-bold">{step}</td><td className="px-4 py-3 font-bold">{layer}</td><td className="px-4 py-3 text-zinc-600">{evidence}</td><td className="px-4 py-3 text-amber-800">{boundary}</td></tr>)}</tbody></table></div></section> }
function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h2 className="mt-1 text-lg font-bold">{title}</h2></div> }
