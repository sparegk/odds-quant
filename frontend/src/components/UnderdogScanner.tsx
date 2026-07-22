import { useMemo, useState } from 'react'
import { AlertTriangle, Filter, ScanSearch } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import type { DashboardData, ValueSignal } from '../types'

type SideFilter = 'ALL' | 'HOME' | 'AWAY'
type SortKey = 'LOWER_EV' | 'EDGE' | 'ODDS' | 'CONFIDENCE'

interface UnderdogScannerProps {
  dashboard: DashboardData
  onOpenEvent: (eventId: number) => void
}

export function UnderdogScanner({ dashboard, onOpenEvent }: UnderdogScannerProps) {
  const [competition, setCompetition] = useState('ALL')
  const [side, setSide] = useState<SideFilter>('ALL')
  const [minimumOdds, setMinimumOdds] = useState('2')
  const [minimumLowerEv, setMinimumLowerEv] = useState('0')
  const [minimumConfidence, setMinimumConfidence] = useState('0')
  const [sort, setSort] = useState<SortKey>('LOWER_EV')

  const eventById = useMemo(() => new Map(dashboard.events.map((event) => [event.id, event])), [dashboard.events])
  const competitions = useMemo(
    () => Array.from(new Set(dashboard.underdogs.map((signal) => eventById.get(signal.event_id)?.competition).filter((value): value is string => Boolean(value)))).sort(),
    [dashboard.underdogs, eventById],
  )
  const filtered = useMemo(() => {
    const oddsFloor = finiteOr(minimumOdds, 0)
    const lowerEvFloor = finiteOr(minimumLowerEv, 0) / 100
    const confidenceFloor = finiteOr(minimumConfidence, 0) / 100
    return dashboard.underdogs
      .filter((signal) => {
        const event = eventById.get(signal.event_id)
        return (competition === 'ALL' || event?.competition === competition)
          && (side === 'ALL' || signal.selection_code === side)
          && signal.offered_odds >= oddsFloor
          && signal.lower_expected_value >= lowerEvFloor
          && signal.confidence >= confidenceFloor
      })
      .sort((left, right) => rankValue(right, sort) - rankValue(left, sort) || right.expected_value - left.expected_value)
  }, [competition, dashboard.underdogs, eventById, minimumConfidence, minimumLowerEv, minimumOdds, side, sort])

  if (!dashboard.underdogs.length) return <UnderdogEvidenceGate />

  const valueCount = filtered.filter((signal) => signal.signal_type === 'VALUE').length
  const bestLowerEv = filtered.length ? Math.max(...filtered.map((signal) => signal.lower_expected_value)) : null

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase text-emerald-700">Positive-EV team outcomes only</p>
          <h2 className="mt-1 text-lg font-bold">Underdog evidence scanner</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">Rank qualified home and away outcomes by conservative model evidence. High odds alone never qualify a selection.</p>
        </div>
        <span className="rounded-[4px] border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-600">{filtered.length} of {dashboard.underdogs.length} shown</span>
      </div>

      <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4">
        <ScannerMetric label="Qualified" value={filtered.length.toString()} />
        <ScannerMetric label="Value signals" value={valueCount.toString()} />
        <ScannerMetric label="Best lower EV" value={bestLowerEv === null ? '—' : signedPercent(bestLowerEv)} />
        <ScannerMetric label="Evidence rule" value="Lower bound" />
      </section>

      <section className="border-y border-zinc-200 bg-white p-4">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold"><Filter aria-hidden="true" size={16} />Scanner controls</div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          <FilterSelect label="Competition" value={competition} onChange={setCompetition} options={[['ALL', 'All competitions'], ...competitions.map((item) => [item, item])]}/>
          <FilterSelect label="Side" value={side} onChange={(value) => setSide(value as SideFilter)} options={[["ALL", "Home or away"], ["HOME", "Home underdog"], ["AWAY", "Away underdog"]]}/>
          <FilterNumber label="Minimum odds" value={minimumOdds} onChange={setMinimumOdds} min="2" step="0.1" />
          <FilterNumber label="Minimum lower EV (%)" value={minimumLowerEv} onChange={setMinimumLowerEv} step="0.5" />
          <FilterNumber label="Minimum confidence (%)" value={minimumConfidence} onChange={setMinimumConfidence} min="0" max="100" step="5" />
          <FilterSelect label="Rank by" value={sort} onChange={(value) => setSort(value as SortKey)} options={[["LOWER_EV", "Conservative EV"], ["EDGE", "Probability edge"], ["CONFIDENCE", "Confidence"], ["ODDS", "Offered odds"]]}/>
        </div>
      </section>

      {filtered.length ? (
        <div className="grid gap-5 xl:grid-cols-2">
          {filtered.map((signal, index) => <UnderdogCard key={signal.id} event={eventById.get(signal.event_id)} rank={index + 1} signal={signal} onOpenEvent={onOpenEvent} />)}
        </div>
      ) : (
        <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center">
          <ScanSearch aria-hidden="true" className="mx-auto text-zinc-400" size={28} />
          <h3 className="mt-3 font-bold">No underdogs match these filters</h3>
          <p className="mt-2 text-sm text-zinc-500">Reduce the odds, conservative EV, or confidence threshold to inspect the stored qualified set.</p>
        </div>
      )}

      <div className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">Rankings keep model probability, market consensus, price improvement, and uncertainty separate. They are research classifications at a stored cutoff, not betting instructions.</div>
    </div>
  )
}

function UnderdogCard({ event, rank, signal, onOpenEvent }: { event: DashboardData['events'][number] | undefined; rank: number; signal: ValueSignal; onOpenEvent: (eventId: number) => void }) {
  return (
    <article className="border border-zinc-200 bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-zinc-200 p-5">
        <div>
          <p className="text-xs font-bold uppercase text-emerald-700">Rank #{rank} · {humanizeCode(signal.selection_code)} underdog</p>
          <h3 className="mt-1 text-lg font-bold">{event ? `${event.home_team} vs ${event.away_team}` : `Event ${signal.event_id}`}</h3>
          <p className="mt-1 text-sm font-semibold text-zinc-700">{signal.selection_name} at {signal.offered_odds.toFixed(2)} · {signal.bookmaker}</p>
          {event ? <p className="mt-1 text-xs text-zinc-500">{event.competition} · {formatDateTime(event.kickoff_at)}</p> : null}
        </div>
        <span className={`rounded-[4px] border px-2.5 py-1 text-xs font-bold ${signal.signal_type === 'VALUE' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-sky-200 bg-sky-50 text-sky-800'}`}>{signal.signal_type}</span>
      </div>
      <div className="grid grid-cols-2 border-b border-zinc-200 sm:grid-cols-3">
        <ScannerMetric label="Model" value={percent(signal.model_probability)} />
        <ScannerMetric label="Market" value={percent(signal.market_fair_probability)} />
        <ScannerMetric label="Edge" value={signedPercent(signal.probability_edge)} />
        <ScannerMetric label="Expected EV" value={signedPercent(signal.expected_value)} />
        <ScannerMetric label="Lower EV" value={signedPercent(signal.lower_expected_value)} />
        <ScannerMetric label="Confidence" value={percent(signal.confidence, 0)} />
      </div>
      <div className="p-5 text-sm leading-6">
        <p className="font-semibold text-zinc-800">{signal.reasons[0] ?? 'Stored quantitative qualification.'}</p>
        {signal.risks[0] ? <p className="mt-2 flex gap-2 text-amber-800"><AlertTriangle aria-hidden="true" className="mt-1 shrink-0" size={15} />{signal.risks[0]}</p> : null}
        <details className="mt-3 border-t border-zinc-100 pt-3 text-xs text-zinc-500">
          <summary className="cursor-pointer font-semibold text-zinc-700">Evidence and provenance</summary>
          <div className="mt-2 grid gap-1">
            <p>Lower probability {percent(signal.lower_probability)} · calibration error {percent(signal.calibration_error)}</p>
            <p>{signal.bookmaker_count} compatible bookmakers · odds age {signal.odds_age_minutes.toFixed(0)} minutes</p>
            <p>Price move {signedPercent(signal.odds_move_ratio)} · evaluation #{signal.evaluation_run_id} · prediction #{signal.prediction_id}</p>
            <p>Generated {formatDateTime(signal.generated_at)} · model {signal.model_version}</p>
          </div>
        </details>
        <button className="mt-4 rounded-[5px] border border-zinc-300 px-3 py-2 text-xs font-bold hover:bg-zinc-50" onClick={() => onOpenEvent(signal.event_id)} type="button">Open event research</button>
      </div>
    </article>
  )
}

function UnderdogEvidenceGate() {
  return <div className="space-y-5"><div className="border-y border-zinc-200 bg-white px-6 py-12 text-center"><ScanSearch aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">No qualified underdogs</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">Underdogs appear only after a non-demo model passes chronological calibration and a team outcome has positive expected value against complete compatible pre-kickoff odds.</p></div><div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">Long odds and demo prices are never treated as value. Generate signals only after valid evidence exists.</div></div>
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><select aria-label={label} className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([optionValue, text]) => <option key={optionValue} value={optionValue}>{text}</option>)}</select></label>
}

function FilterNumber({ label, value, onChange, min, max, step }: { label: string; value: string; onChange: (value: string) => void; min?: string; max?: string; step: string }) {
  return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} className="h-10 w-full border border-zinc-300 px-3 text-sm" min={min} max={max} step={step} type="number" value={value} onChange={(event) => onChange(event.target.value)} /></label>
}

function ScannerMetric({ label, value }: { label: string; value: string }) {
  return <div className="border-r border-b border-zinc-200 p-4 last:border-r-0"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono font-bold">{value}</p></div>
}

function rankValue(signal: ValueSignal, sort: SortKey): number {
  if (sort === 'EDGE') return signal.probability_edge
  if (sort === 'ODDS') return signal.offered_odds
  if (sort === 'CONFIDENCE') return signal.confidence
  return signal.lower_expected_value
}

function finiteOr(value: string, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function percent(value: number, digits = 1): string { return `${(value * 100).toFixed(digits)}%` }
function signedPercent(value: number): string { return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` }
