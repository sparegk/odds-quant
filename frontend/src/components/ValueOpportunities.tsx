import { useMemo } from 'react'
import { AlertTriangle, Filter, TrendingUp } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import { useResearchPreference } from '../lib/researchPreferences'
import type { DashboardData, RecommendationSnapshot, ResearchValueCandidate, ValueSignal } from '../types'

type ValueSort = 'LOWER_EV' | 'EDGE' | 'CONFIDENCE' | 'FRESHNESS'

export function ValueOpportunities({ dashboard, onOpenEvent }: { dashboard: DashboardData; onOpenEvent: (eventId: number) => void }) {
  const [competition, setCompetition] = useResearchPreference('value_competition', 'ALL')
  const [market, setMarket] = useResearchPreference('value_market', 'ALL')
  const [minimumLowerEv, setMinimumLowerEv] = useResearchPreference('value_min_ev', '0')
  const [minimumConfidence, setMinimumConfidence] = useResearchPreference('value_min_confidence', '0')
  const [sortPreference, setSort] = useResearchPreference('value_sort', 'LOWER_EV', (value) => ['LOWER_EV', 'EDGE', 'CONFIDENCE', 'FRESHNESS'].includes(value))
  const sort = sortPreference as ValueSort
  const events = useMemo(() => new Map(dashboard.events.map((event) => [event.id, event])), [dashboard.events])
  const researchCandidates = dashboard.research_candidates ?? []
  const trackedRecommendations = dashboard.tracked_recommendations ?? []
  const competitions = unique(dashboard.signals.map((signal) => events.get(signal.event_id)?.competition))
  const markets = unique(dashboard.signals.map((signal) => signal.market_type))
  const filtered = useMemo(() => dashboard.signals
    .filter((signal) => (competition === 'ALL' || events.get(signal.event_id)?.competition === competition)
      && (market === 'ALL' || signal.market_type === market)
      && signal.lower_expected_value >= numberOr(minimumLowerEv, 0) / 100
      && signal.confidence >= numberOr(minimumConfidence, 0) / 100)
    .sort((left, right) => sortValue(right, sort) - sortValue(left, sort) || right.expected_value - left.expected_value),
  [competition, dashboard.signals, events, market, minimumConfidence, minimumLowerEv, sort])

  if (!dashboard.signals.length && !researchCandidates.length && !trackedRecommendations.length) {
    return <div className="space-y-5"><EmptyValue title="No value research for upcoming matches" detail="The screen will populate when an upcoming non-demo prediction joins a complete compatible pre-kickoff price." /><div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">Qualified VALUE recommendations still require chronological calibration, fresh prices, adequate samples, and positive conservative EV.</div></div>
  }

  const averageLowerEv = filtered.length ? filtered.reduce((sum, signal) => sum + signal.lower_expected_value, 0) / filtered.length : null
  const freshest = filtered.length ? Math.min(...filtered.map((signal) => signal.odds_age_minutes)) : null
  const positiveRawEv = researchCandidates.filter((candidate) => candidate.expected_value > 0).length
  const evaluations = new Map(dashboard.evaluations.map((run) => [run.id, run]))
  const linkedSignals = dashboard.signals.filter((signal) => {
    const run = evaluations.get(signal.evaluation_run_id)
    return Boolean(run && !run.is_demo && run.evaluation_status === 'calibrated')
  }).length

  return <div className="space-y-7">
    <div><p className="text-xs font-bold uppercase text-emerald-700">Upcoming evidence versus market</p><h2 className="mt-1 text-lg font-bold">Value opportunity research</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">Qualified recommendations and exploratory model/price disagreements are kept separate. Research-only gaps show what looks interesting and exactly why it is not yet a VALUE signal.</p></div>
    <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4"><ValueMetric label="Qualified VALUE" value={dashboard.signals.length.toString()} /><ValueMetric label="Research gaps" value={researchCandidates.length.toString()} /><ValueMetric label="Positive raw EV" value={positiveRawEv.toString()} /><ValueMetric label="Policy" value="Fail closed" /></section>
    {trackedRecommendations.length ? <TrackedRecommendations records={trackedRecommendations} /> : null}
    {dashboard.signals.length ? <SignalEvidenceAudit signals={dashboard.signals} linkedSignals={linkedSignals} /> : null}
    {researchCandidates.length ? <section className="space-y-4"><div><p className="text-xs font-bold uppercase text-amber-700">Upcoming watchlist</p><h3 className="mt-1 font-bold">Research-only candidates</h3><p className="mt-1 text-sm leading-6 text-zinc-500">Ranked by raw model EV before calibration. Never treat these as recommendations while any listed gate remains blocked.</p></div>{researchCandidates.map((candidate, index) => <ResearchCandidateCard candidate={candidate} key={`${candidate.output_id}-${candidate.selection_id}`} rank={index + 1} onOpenEvent={onOpenEvent} />)}</section> : null}
    {dashboard.signals.length ? <>
      <div><p className="text-xs font-bold uppercase text-emerald-700">Qualified set</p><h3 className="mt-1 font-bold">Calibrated VALUE recommendations</h3></div>
      <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-3"><ValueMetric label="Recommendations shown" value={filtered.length.toString()} /><ValueMetric label="Average lower EV" value={averageLowerEv === null ? '—' : signedPercent(averageLowerEv)} /><ValueMetric label="Freshest price" value={freshest === null ? '—' : `${freshest.toFixed(0)}m`} /></section>
      <section className="border-y border-zinc-200 bg-white p-4"><div className="mb-4 flex items-center gap-2 text-sm font-bold"><Filter aria-hidden="true" size={16} />Qualified-signal controls</div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Select label="Competition" value={competition} onChange={setCompetition} options={[["ALL", "All competitions"], ...competitions.map((value) => [value, value])]} />
        <Select label="Market" value={market} onChange={setMarket} options={[["ALL", "All markets"], ...markets.map((value) => [value, humanizeCode(value)])]} />
        <NumberFilter label="Minimum lower EV (%)" value={minimumLowerEv} onChange={setMinimumLowerEv} />
        <NumberFilter label="Minimum confidence (%)" value={minimumConfidence} onChange={setMinimumConfidence} max="100" />
        <Select label="Rank by" value={sort} onChange={setSort} options={[["LOWER_EV", "Conservative EV"], ["EDGE", "Probability edge"], ["CONFIDENCE", "Confidence"], ["FRESHNESS", "Freshest price"]]} />
      </div></section>
      {filtered.length ? <div className="space-y-4">{filtered.map((signal, index) => <ValueCard key={signal.id} event={events.get(signal.event_id)} rank={index + 1} signal={signal} onOpenEvent={onOpenEvent} />)}</div> : <EmptyValue title="No opportunities match these filters" detail="Reduce the conservative EV or confidence threshold, or choose a broader competition and market." />}
    </> : <EmptyValue title="No qualified VALUE recommendations yet" detail="The watchlist above remains visible while calibration, sample, uncertainty, freshness, and market-coverage gates are unresolved." />}
    <div className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">Model edge, raw expected value, conservative qualified value, line-shopping improvement, and bookmaker margin remain separate quantities.</div>
  </div>
}

function TrackedRecommendations({ records }: { records: RecommendationSnapshot[] }) {
  return <section className="space-y-3" aria-labelledby="prospective-tracking-title"><div><p className="text-xs font-bold uppercase text-sky-700">Prospective evidence</p><h3 className="mt-1 font-bold" id="prospective-tracking-title">Tracked recommendation outcomes</h3><p className="mt-1 text-sm leading-6 text-zinc-500">Decision-time inputs are immutable. Closing-line and settlement states update separately and never rewrite the original edge.</p></div><div className="space-y-2">{records.map((record) => <article className="grid gap-3 border border-zinc-200 bg-white p-4 text-sm md:grid-cols-[1fr_repeat(4,auto)] md:items-center" key={record.id}><div><p className="font-bold">{humanizeCode(record.market_type)} / {humanizeCode(record.selection_code)}</p><p className="mt-1 text-xs text-zinc-500">Captured {formatDateTime(record.captured_at)} / fingerprint {record.fingerprint.slice(0, 12)}</p></div><CompactMetric label="Taken odds" value={record.offered_odds.toFixed(2)} /><CompactMetric label="Lower net EV" value={signedPercent(record.lower_net_expected_value)} /><CompactMetric label="Closing line" value={trackedClosingLine(record)} /><CompactMetric label="Settlement" value={record.tracking.settlement_status === 'SETTLED' ? record.tracking.settlement ?? 'UNKNOWN' : 'PENDING'} /></article>)}</div></section>
}

function trackedClosingLine(record: RecommendationSnapshot): string {
  if (record.tracking.closing_line_status !== 'AVAILABLE' || record.tracking.closing_odds === null) return record.tracking.closing_line_status
  const clv = record.tracking.closing_line_value
  return `${record.tracking.closing_odds.toFixed(2)}${clv === null ? '' : ` / ${signedPercent(clv)} CLV`}`
}

function SignalEvidenceAudit({ signals, linkedSignals }: { signals: ValueSignal[]; linkedSignals: number }) {
  const scenarios = [
    ['Stored qualified set', signals.length],
    ['Lower EV at least 2%', signals.filter((signal) => signal.lower_expected_value >= 0.02).length],
    ['Lower EV at least 5%', signals.filter((signal) => signal.lower_expected_value >= 0.05).length],
    ['Confidence at least 80%', signals.filter((signal) => signal.confidence >= 0.8).length],
  ] as const
  const complete = linkedSignals === signals.length
  return <section aria-labelledby="value-sensitivity-title"><div className="mb-3"><p className="text-xs font-bold uppercase text-sky-700">Evidence audit</p><h3 className="mt-1 font-bold" id="value-sensitivity-title">Calibration and threshold sensitivity</h3></div><div className={`border-l-4 p-4 ${complete ? 'border-emerald-500 bg-emerald-50' : 'border-amber-400 bg-amber-50'}`}><p className="font-bold">{linkedSignals} of {signals.length} signals link to a loaded non-demo calibrated evaluation</p><p className="mt-1 text-xs leading-5 text-zinc-700">Missing dashboard linkage blocks independent verification in this view; it does not rewrite immutable stored signal status.</p><dl className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">{scenarios.map(([label, count]) => <div className="border border-black/10 bg-white/80 p-3" key={label}><dt className="text-xs font-semibold text-zinc-600">{label}</dt><dd className="mt-1 font-mono text-lg font-bold">{count}</dd></div>)}</dl><p className="mt-3 text-xs leading-5 text-zinc-600">These scenarios only show how the current stored set changes under stricter display thresholds. They are not optimized policies or retrospective profitability evidence.</p></div></section>
}

function ResearchCandidateCard({ candidate, rank, onOpenEvent }: { candidate: ResearchValueCandidate; rank: number; onOpenEvent: (eventId: number) => void }) {
  return <article className="border border-amber-200 bg-white"><div className="grid gap-4 p-5 lg:grid-cols-[minmax(260px,1fr)_repeat(5,minmax(90px,auto))] lg:items-center">
    <div><p className="text-xs font-bold uppercase text-amber-700">Research #{rank} · not qualified</p><h4 className="mt-1 font-bold">{candidate.home_team} vs {candidate.away_team}</h4><p className="mt-1 text-sm text-zinc-600">{candidate.selection_name} · <strong>{candidate.offered_odds.toFixed(2)}</strong> at {candidate.bookmaker}</p><p className="mt-1 text-xs text-zinc-500">{candidate.competition} · {formatDateTime(candidate.kickoff_at)}</p></div>
    <CompactMetric label="Model" value={percent(candidate.model_probability)} /><CompactMetric label="Market" value={percent(candidate.market_fair_probability)} /><CompactMetric label="Edge" value={signedPercent(candidate.probability_edge)} /><CompactMetric label="Raw EV" value={signedPercent(candidate.expected_value)} /><CompactMetric label="Lower EV" value={signedPercent(candidate.lower_expected_value)} />
  </div><div className="grid gap-3 border-t border-amber-200 bg-amber-50 px-5 py-4 text-xs md:grid-cols-[1fr_auto] md:items-start"><div><p className="font-bold uppercase text-amber-900">Why it cannot qualify</p><ul className="mt-1 list-disc space-y-1 pl-4 text-amber-950">{candidate.qualification_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul><details className="mt-3 text-zinc-600"><summary className="cursor-pointer font-semibold">Research provenance and risks</summary><p className="mt-1">Model interval {percent(candidate.lower_probability)}–{percent(candidate.upper_probability)} · {candidate.bookmaker_count} book(s) · price age {candidate.odds_age_minutes.toFixed(0)}m</p><p>Model {candidate.model_version} ({candidate.model_evaluation_status}) · prediction #{candidate.prediction_id} · snapshot #{candidate.odds_snapshot_id}</p><p>Observed {formatDateTime(candidate.odds_observed_at)} · evidence {humanizeCode(candidate.evidence_class)}</p>{candidate.risks.map((risk) => <p className="mt-1 flex gap-1.5 text-amber-800" key={risk}><AlertTriangle aria-hidden="true" size={14} />{risk}</p>)}</details></div><button className="rounded-[5px] border border-amber-300 bg-white px-3 py-2 font-bold hover:bg-amber-100" onClick={() => onOpenEvent(candidate.event_id)} type="button">Open event</button></div>
  </article>
}

function ValueCard({ event, rank, signal, onOpenEvent }: { event: DashboardData['events'][number] | undefined; rank: number; signal: ValueSignal; onOpenEvent: (eventId: number) => void }) {
  return <article className="border border-zinc-200 bg-white"><div className="grid gap-4 p-5 lg:grid-cols-[minmax(260px,1fr)_repeat(5,minmax(90px,auto))] lg:items-center">
    <div><p className="text-xs font-bold uppercase text-emerald-700">Rank #{rank} · {humanizeCode(signal.market_type)}</p><h3 className="mt-1 font-bold">{event ? `${event.home_team} vs ${event.away_team}` : `Event ${signal.event_id}`}</h3><p className="mt-1 text-sm text-zinc-600">{signal.selection_name} · <strong>{signal.offered_odds.toFixed(2)}</strong> at {signal.bookmaker}</p>{event ? <p className="mt-1 text-xs text-zinc-500">{event.competition} · {formatDateTime(event.kickoff_at)}</p> : null}</div>
    <CompactMetric label="Model" value={percent(signal.model_probability)} /><CompactMetric label="Market" value={percent(signal.market_fair_probability)} /><CompactMetric label="Edge" value={signedPercent(signal.probability_edge)} /><CompactMetric label="EV" value={signedPercent(signal.expected_value)} /><CompactMetric label="Lower EV" value={signedPercent(signal.lower_expected_value)} tone />
  </div><div className="grid gap-3 border-t border-zinc-200 bg-zinc-50 px-5 py-4 text-xs md:grid-cols-[1fr_auto] md:items-start"><div><p className="font-semibold text-zinc-700">{signal.reasons[0] ?? 'Stored calibrated recommendation.'}</p>{signal.risks[0] ? <p className="mt-1 flex gap-1.5 text-amber-800"><AlertTriangle aria-hidden="true" size={14} />{signal.risks[0]}</p> : null}<details className="mt-2 text-zinc-500"><summary className="cursor-pointer font-semibold">Full evidence</summary><p className="mt-1">Confidence {percent(signal.confidence)} · lower probability {percent(signal.lower_probability)} · calibration error {percent(signal.calibration_error)}</p><p>{signal.bookmaker_count} books · {signal.odds_age_minutes.toFixed(0)}m old · move {signedPercent(signal.odds_move_ratio)} · eval #{signal.evaluation_run_id}</p><p>Prediction #{signal.prediction_id} · snapshot #{signal.odds_snapshot_id} · generated {formatDateTime(signal.generated_at)}</p></details></div><button className="rounded-[5px] border border-zinc-300 bg-white px-3 py-2 font-bold hover:bg-zinc-100" onClick={() => onOpenEvent(signal.event_id)} type="button">Open event</button></div>
  </article>
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><select aria-label={label} className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label> }
function NumberFilter({ label, value, onChange, max }: { label: string; value: string; onChange: (value: string) => void; max?: string }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} className="h-10 w-full border border-zinc-300 px-3 text-sm" max={max} step="0.5" type="number" value={value} onChange={(event) => onChange(event.target.value)} /></label> }
function ValueMetric({ label, value }: { label: string; value: string }) { return <div className="border-r border-b border-zinc-200 p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-2 text-xl font-bold">{value}</p></div> }
function CompactMetric({ label, value, tone = false }: { label: string; value: string; tone?: boolean }) { return <div><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className={`mt-1 font-mono font-bold ${tone ? 'text-emerald-700' : ''}`}>{value}</p></div> }
function EmptyValue({ title, detail }: { title: string; detail: string }) { return <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center"><TrendingUp aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">{title}</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{detail}</p></div> }
function unique(values: Array<string | undefined>): string[] { return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort() }
function numberOr(value: string, fallback: number): number { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback }
function sortValue(signal: ValueSignal, sort: ValueSort): number { if (sort === 'EDGE') return signal.probability_edge; if (sort === 'CONFIDENCE') return signal.confidence; if (sort === 'FRESHNESS') return -signal.odds_age_minutes; return signal.lower_expected_value }
function percent(value: number): string { return `${(value * 100).toFixed(1)}%` }
function signedPercent(value: number): string { return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` }
