import {
  AlertTriangle,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Clock3,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { loadMatchday, loadMatchdayEvent } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type {
  BetBuilderQuote,
  Matchday,
  MatchdayCompetition,
  MatchdayEvent,
  MatchdayEventDetail,
  MarketComparison,
  ResearchGate,
  SnapshotComparison,
  TeamForm,
} from '../types'

const competitionFilters = [
  { key: 'all', label: 'All tracked' },
  { key: 'champions-league', label: 'Champions League' },
  { key: 'premier-league', label: 'Premier League' },
  { key: 'la-liga', label: 'La Liga' },
  { key: 'bundesliga', label: 'Bundesliga' },
  { key: 'ligue-1', label: 'Ligue 1' },
  { key: 'europa-league', label: 'Europa League' },
  { key: 'conference-league', label: 'Conference League' },
  { key: 'top-cups', label: 'Top cups' },
  { key: 'major-events', label: 'Major events' },
] as const

function localDateString(date: Date): string {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00`)
  date.setDate(date.getDate() + days)
  return localDateString(date)
}

function kickoffTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function percentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function signedPercentage(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

function findFirstEvent(competitions: MatchdayCompetition[]): number | null {
  return competitions[0]?.events[0]?.event.id ?? null
}

export function MatchdayResearch({ onSelectEvent }: { onSelectEvent: (eventId: number) => void }) {
  const [date, setDate] = useState(() => localDateString(new Date()))
  const [timezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Athens',
  )
  const [filter, setFilter] = useState<(typeof competitionFilters)[number]['key']>('all')
  const [schedule, setSchedule] = useState<Matchday | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [detail, setDetail] = useState<MatchdayEventDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void loadMatchday(date, timezone)
      .then((loaded) => {
        if (!active) return
        setSchedule(loaded)
        const first = findFirstEvent(loaded.competitions)
        setSelectedEventId(first)
        setDetailLoading(first !== null)
        setDetailError(null)
        if (first !== null) onSelectEvent(first)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setSchedule(null)
        setSelectedEventId(null)
        setError(caught instanceof Error ? caught.message : 'Unable to load this matchday')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [date, onSelectEvent, timezone])

  useEffect(() => {
    if (selectedEventId === null) {
      return
    }
    let active = true
    void loadMatchdayEvent(selectedEventId)
      .then((loaded) => {
        if (active) setDetail(loaded)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setDetail(null)
        setDetailError(caught instanceof Error ? caught.message : 'Unable to load match research')
      })
      .finally(() => {
        if (active) setDetailLoading(false)
      })
    return () => {
      active = false
    }
  }, [selectedEventId])

  const filteredCompetitions = useMemo(
    () => schedule?.competitions.filter((competition) => filter === 'all' || competition.group_key === filter) ?? [],
    [filter, schedule],
  )
  const filteredCount = filteredCompetitions.reduce((total, competition) => total + competition.events.length, 0)

  const chooseDate = (next: string) => {
    if (!next) return
    setLoading(true)
    setError(null)
    setSchedule(null)
    setSelectedEventId(null)
    setDetail(null)
    setDetailError(null)
    setDate(next)
  }

  const selectEvent = (eventId: number) => {
    setDetailLoading(true)
    setDetailError(null)
    setDetail(null)
    setSelectedEventId(eventId)
    onSelectEvent(eventId)
  }

  return (
    <div className="space-y-6">
      <section className="border border-zinc-200 bg-white">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-zinc-200 p-5">
          <div>
            <p className="text-xs font-bold uppercase text-emerald-700">Fixture-first research</p>
            <h2 className="mt-1 text-xl font-bold">Matchday</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">
              Pick a day, open a match, then separate likely outcomes from evidence-backed value and the best available price.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous day"
              className="grid h-10 w-10 place-items-center border border-zinc-300 hover:bg-zinc-50"
              onClick={() => chooseDate(shiftDate(date, -1))}
              type="button"
            >
              <ChevronLeft aria-hidden="true" size={17} />
            </button>
            <label className="relative">
              <span className="sr-only">Matchday date</span>
              <CalendarDays aria-hidden="true" className="pointer-events-none absolute left-3 top-3 text-zinc-400" size={16} />
              <input
                className="h-10 border border-zinc-300 bg-white pl-9 pr-3 text-sm font-semibold"
                onChange={(event) => chooseDate(event.target.value)}
                type="date"
                value={date}
              />
            </label>
            <button
              aria-label="Next day"
              className="grid h-10 w-10 place-items-center border border-zinc-300 hover:bg-zinc-50"
              onClick={() => chooseDate(shiftDate(date, 1))}
              type="button"
            >
              <ChevronRight aria-hidden="true" size={17} />
            </button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto p-3" aria-label="Competition filters">
          {competitionFilters.map((item) => (
            <button
              key={item.key}
              className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold ${
                filter === item.key
                  ? 'border-zinc-900 bg-zinc-900 text-white'
                  : 'border-zinc-300 bg-white text-zinc-600 hover:border-zinc-500'
              }`}
              onClick={() => setFilter(item.key)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {error ? <MatchdayError message={error} /> : null}
      {loading ? <MatchdayLoading label="Loading fixtures" /> : null}
      {!loading && schedule ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
            <p><strong className="text-zinc-800">{filteredCount}</strong> matches / {timezone}</p>
            <p>Data cutoff {formatDateTime(schedule.as_of)}</p>
          </div>
          {filteredCount ? (
            <div className="grid items-start gap-6 xl:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
              <div className="space-y-4">
                {filteredCompetitions.map((competition) => (
                  <CompetitionCard
                    competition={competition}
                    key={competition.competition_id}
                    onSelect={selectEvent}
                    selectedEventId={selectedEventId}
                  />
                ))}
              </div>
              <div className="min-w-0 xl:sticky xl:top-24">
                {detailLoading ? <MatchdayLoading label="Loading match research" /> : null}
                {detailError ? <MatchdayError message={detailError} /> : null}
                {!detailLoading && detail ? <MatchDetail detail={detail} /> : null}
              </div>
            </div>
          ) : (
            <EmptyMatchday filter={filter} />
          )}
          <p className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">
            {schedule.data_note}
          </p>
        </>
      ) : null}
    </div>
  )
}

function CompetitionCard({
  competition,
  selectedEventId,
  onSelect,
}: {
  competition: MatchdayCompetition
  selectedEventId: number | null
  onSelect: (eventId: number) => void
}) {
  return (
    <section className="overflow-hidden border border-zinc-200 bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-200 bg-zinc-50 px-4 py-3">
        <div>
          <p className="text-xs font-bold uppercase text-emerald-700">{competition.group_label}</p>
          <h3 className="mt-0.5 font-bold">{competition.name}</h3>
        </div>
        <span className="text-xs text-zinc-500">{competition.country}</span>
      </div>
      {competition.events.map((item) => (
        <FixtureButton
          active={selectedEventId === item.event.id}
          item={item}
          key={item.event.id}
          onSelect={onSelect}
        />
      ))}
    </section>
  )
}

function FixtureButton({ item, active, onSelect }: { item: MatchdayEvent; active: boolean; onSelect: (eventId: number) => void }) {
  return (
    <button
      className={`grid w-full grid-cols-[54px_1fr] gap-3 border-b border-zinc-100 px-4 py-4 text-left last:border-0 ${
        active ? 'bg-emerald-50' : 'hover:bg-zinc-50'
      }`}
      onClick={() => onSelect(item.event.id)}
      type="button"
    >
      <div className="pt-0.5 text-center">
        <p className="font-mono text-sm font-bold">{kickoffTime(item.event.kickoff_at)}</p>
        <p className="mt-1 text-[10px] font-bold uppercase text-zinc-400">{item.event.status}</p>
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{item.event.home_team}</p>
        <p className="mt-1 truncate text-sm font-semibold">{item.event.away_team}</p>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] font-semibold uppercase text-zinc-500">
          <span>{item.market_count} markets</span>
          <span>·</span>
          <span>{item.bookmaker_count} books</span>
          {item.latest_prediction_at ? <><span>·</span><span>model</span></> : null}
          {item.qualified_signal_count ? <span className="text-emerald-700">· {item.qualified_signal_count} value</span> : null}
        </div>
      </div>
    </button>
  )
}

function MatchDetail({ detail }: { detail: MatchdayEventDetail }) {
  const likely = [...(detail.latest_prediction?.predictions ?? [])].sort((left, right) => right.probability - left.probability)
  const bestPrices = detail.markets.flatMap((market) => market.best_prices.map((price) => ({ market, price })))
  const builderQuotes = [...detail.builder_quotes].sort((left, right) => (right.lower_expected_value ?? -1) - (left.lower_expected_value ?? -1))

  return (
    <article className="border border-zinc-200 bg-white">
      <header className="border-b border-zinc-200 p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase text-emerald-700">
          <span>{detail.competition_group_label}</span>
          {detail.event.is_demo ? <span className="border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-800">Demo data</span> : null}
        </div>
        <h2 className="mt-2 text-xl font-bold">{detail.event.home_team} <span className="font-normal text-zinc-400">vs</span> {detail.event.away_team}</h2>
        <p className="mt-1 flex items-center gap-1.5 text-sm text-zinc-500"><Clock3 aria-hidden="true" size={14} />{formatDateTime(detail.event.kickoff_at)}</p>
      </header>

      <div className="space-y-7 p-5">
        <section>
          <DetailHeading eyebrow="Probability versus price" title="Research candidates" />
          {detail.signals.length ? (
            <div className="space-y-3">
              {detail.signals.map((signal) => (
                <div className="border border-emerald-200 bg-emerald-50 p-4" key={signal.id}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><p className="text-xs font-bold uppercase text-emerald-700">Evidence-backed {humanizeCode(signal.signal_type)}</p><p className="mt-1 font-bold">{signal.selection_name}</p></div>
                    <p className="font-mono font-bold">{signal.bookmaker} @ {signal.offered_odds.toFixed(2)}</p>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <EvidenceMetric label="Model" value={percentage(signal.model_probability)} />
                    <EvidenceMetric label="Market" value={percentage(signal.market_fair_probability)} />
                    <EvidenceMetric label="Lower EV" value={signedPercentage(signal.lower_expected_value)} />
                  </div>
                  <p className="mt-3 text-xs leading-5 text-emerald-950">{signal.reasons[0]}</p>
                </div>
              ))}
            </div>
          ) : likely.length ? (
            <div>
              <div className="mb-3 border-l-4 border-amber-400 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                Likelihood only—not a betting edge. No calibrated price signal is stored at this cutoff.
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                {likely.slice(0, 3).map((prediction) => (
                  <div className="border border-zinc-200 p-3" key={prediction.id}>
                    <p className="text-xs font-semibold text-zinc-500">{prediction.selection_name}</p>
                    <p className="mt-2 text-xl font-bold">{percentage(prediction.probability)}</p>
                    <p className="mt-1 text-xs text-zinc-500">Fair odds {prediction.fair_odds.toFixed(2)} / lower {percentage(prediction.lower_probability)}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <ResearchEmpty text="No timestamp-valid pre-kickoff model output is stored for this match." />
          )}
          <p className="mt-3 text-xs leading-5 text-zinc-500">{detail.evidence_note}</p>
        </section>

        <section>
          <DetailHeading eyebrow="Line shopping" title="Best bookmaker by selection" />
          {bestPrices.length ? (
            <div className="overflow-x-auto border-y border-zinc-200">
              <table className="w-full min-w-[580px] text-left text-sm">
                <thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-3 py-2.5">Market</th><th className="px-3 py-2.5">Selection</th><th className="px-3 py-2.5">Bookmaker</th><th className="px-3 py-2.5 text-right">Odds</th></tr></thead>
                <tbody>{bestPrices.map(({ market, price }) => <tr className="border-t border-zinc-100" key={`${market.market_id}-${price.selection_code}`}><td className="px-3 py-2.5">{humanizeCode(market.market_type)}{market.line === null ? '' : ` ${market.line}`}</td><td className="px-3 py-2.5 font-semibold">{price.selection_name}</td><td className="px-3 py-2.5">{price.bookmaker}</td><td className="px-3 py-2.5 text-right font-mono font-bold">{price.decimal_odds.toFixed(2)}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <ResearchEmpty text="No complete timestamp-valid bookmaker comparison is stored." />}
          {detail.markets.length ? (
            <div className="mt-4 space-y-3">{detail.markets.map((market) => <MarketSnapshotStats key={market.market_id} market={market} />)}</div>
          ) : null}
          <p className="mt-3 text-xs leading-5 text-zinc-500">{detail.bookmaker_guidance}</p>
        </section>

        <section>
          <DetailHeading eyebrow="Before-kickoff evidence" title="Recent team form" />
          <div className="grid gap-3 sm:grid-cols-2">{detail.team_form.map((form) => <TeamFormCard form={form} key={form.team_id} />)}</div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <ResearchGateCard gate={detail.player_research} icon="players" />
          <div>
            <ResearchGateCard gate={detail.builder_value} icon="builder" />
            {builderQuotes.length ? <BuilderQuotes quotes={builderQuotes} /> : null}
          </div>
        </section>
      </div>
    </article>
  )
}

function MarketSnapshotStats({ market }: { market: MarketComparison }) {
  return (
    <div className="border border-zinc-200">
      <div className="flex flex-wrap items-start justify-between gap-2 bg-zinc-50 px-3 py-2.5">
        <div>
          <p className="text-sm font-bold">{humanizeCode(market.market_type)}{market.line === null ? '' : ` ${market.line}`}</p>
          <p className="mt-0.5 text-[11px] text-zinc-500">{humanizeCode(market.period)} ? {market.currency}</p>
        </div>
        <p className="max-w-xs text-right text-[11px] text-zinc-500">Settlement: {humanizeCode(market.settlement_rule_key)}</p>
      </div>
      {market.snapshots.length ? market.snapshots.map((snapshot) => (
        <SnapshotStats key={snapshot.snapshot_id} snapshot={snapshot} />
      )) : <p className="border-t border-zinc-100 px-3 py-3 text-xs text-zinc-500">No complete snapshot details are available for this market.</p>}
    </div>
  )
}

function SnapshotStats({ snapshot }: { snapshot: SnapshotComparison }) {
  return (
    <div className="border-t border-zinc-100 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold">{snapshot.bookmaker}</p>
            <span className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase ${snapshot.is_stale ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-emerald-300 bg-emerald-50 text-emerald-800'}`}>{snapshot.is_stale ? 'stale' : 'fresh'}</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">Observed {formatDateTime(snapshot.observed_at)} ? source updated {formatDateTime(snapshot.source_updated_at)}</p>
        </div>
        <div className="grid grid-cols-3 gap-4 text-right text-[11px]">
          <StatValue label="Age" value={formatAge(snapshot.freshness_seconds)} />
          <StatValue label="Overround" value={percentage(snapshot.overround)} />
          <StatValue label="Margin" value={percentage(snapshot.bookmaker_margin)} />
        </div>
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[610px] text-left text-xs">
          <thead className="text-[10px] uppercase text-zinc-500"><tr><th className="pb-2">Selection</th><th className="pb-2 text-right">Odds</th><th className="pb-2 text-right">Raw implied</th><th className="pb-2 text-right">Fair probability</th><th className="pb-2 text-right">Fair odds</th></tr></thead>
          <tbody>{snapshot.prices.map((price) => <tr className="border-t border-zinc-100" key={price.selection_code}><td className="py-2 font-semibold">{price.selection_name}</td><td className="py-2 text-right font-mono font-bold">{price.decimal_odds.toFixed(2)}</td><td className="py-2 text-right font-mono">{percentage(price.raw_implied_probability)}</td><td className="py-2 text-right font-mono">{percentage(price.proportional_fair_probability)}</td><td className="py-2 text-right font-mono">{price.proportional_fair_odds.toFixed(2)}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function StatValue({ label, value }: { label: string; value: string }) {
  return <div><p className="uppercase text-zinc-400">{label}</p><p className="mt-0.5 font-mono font-bold text-zinc-700">{value}</p></div>
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

function TeamFormCard({ form }: { form: TeamForm }) {
  return (
    <div className="border border-zinc-200 p-4">
      <div className="flex items-start justify-between gap-3"><div><h4 className="font-bold">{form.team}</h4><p className="mt-0.5 text-xs text-zinc-500">Last {form.sample_size} stored finals</p></div><p className="font-mono text-sm font-bold">{form.points_per_game === null ? '—' : `${form.points_per_game.toFixed(2)} PPG`}</p></div>
      <div className="mt-3 grid grid-cols-3 border-y border-zinc-100 py-2 text-center text-xs"><div><strong className="block text-base text-emerald-700">{form.wins}</strong>W</div><div><strong className="block text-base">{form.draws}</strong>D</div><div><strong className="block text-base text-rose-700">{form.losses}</strong>L</div></div>
      <p className="mt-3 text-xs text-zinc-500">Goals {form.goals_for}–{form.goals_against} / {form.clean_sheets} clean sheets</p>
      <div className="mt-3 flex flex-wrap gap-1.5">{form.results.map((result) => <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold ${result.outcome === 'W' ? 'bg-emerald-100 text-emerald-800' : result.outcome === 'D' ? 'bg-zinc-200 text-zinc-700' : 'bg-rose-100 text-rose-800'}`} key={result.event_id} title={`${result.venue} vs ${result.opponent}, ${result.goals_for}-${result.goals_against}`}>{result.outcome}</span>)}</div>
      {form.warnings.map((warning) => <p className="mt-2 text-xs text-amber-700" key={warning}>{warning}</p>)}
    </div>
  )
}

function ResearchGateCard({ gate, icon }: { gate: ResearchGate; icon: 'players' | 'builder' }) {
  const Icon = icon === 'players' ? Users : Sparkles
  const ready = gate.status === 'available'
  return (
    <div className={`h-full border p-4 ${ready ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}>
      <div className="flex items-start gap-3"><Icon aria-hidden="true" className={ready ? 'text-emerald-700' : 'text-amber-700'} size={20} /><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold">{gate.title}</h3><span className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase ${ready ? 'border-emerald-300 text-emerald-800' : 'border-amber-300 text-amber-800'}`}>{gate.status}</span></div><p className="mt-1 text-xs text-zinc-600">{gate.available_records} relevant stored records</p></div></div>
      <ul className="mt-3 space-y-2 text-xs leading-5 text-zinc-700">{gate.reasons.map((reason) => <li className="flex gap-2" key={reason}>{ready ? <CircleCheck aria-hidden="true" className="mt-0.5 shrink-0 text-emerald-700" size={14} /> : <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-700" size={14} />}{reason}</li>)}</ul>
    </div>
  )
}

function BuilderQuotes({ quotes }: { quotes: BetBuilderQuote[] }) {
  return <div className="mt-2 space-y-2">{quotes.slice(0, 3).map((quote) => {
    const qualified = !quote.is_demo && quote.lower_expected_value !== null && quote.lower_expected_value > 0
    return <div className="border border-zinc-200 bg-white p-3 text-xs" key={quote.id}><div className="flex items-start justify-between gap-2"><p className="font-semibold">{quote.legs.map((leg) => `${humanizeCode(leg.selection)} ${leg.line ?? ''}`.trim()).join(' + ')}</p><span className={`font-bold ${qualified ? 'text-emerald-700' : 'text-zinc-500'}`}>{qualified ? 'VALUE' : 'RESEARCH'}</span></div><p className="mt-1 text-zinc-500">Joint {percentage(quote.joint_probability)} / fair {quote.fair_odds.toFixed(2)} / offered {quote.offered_odds?.toFixed(2) ?? 'not entered'}</p></div>
  })}</div>
}

function DetailHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h3 className="mt-1 text-lg font-bold">{title}</h3></div>
}

function EvidenceMetric({ label, value }: { label: string; value: string }) {
  return <div className="border-l border-emerald-200 pl-2 first:border-0 first:pl-0"><p className="text-emerald-800">{label}</p><p className="mt-0.5 font-mono font-bold text-emerald-950">{value}</p></div>
}

function ResearchEmpty({ text }: { text: string }) {
  return <div className="border border-zinc-200 bg-zinc-50 px-4 py-6 text-center text-sm text-zinc-500">{text}</div>
}

function EmptyMatchday({ filter }: { filter: string }) {
  return <div className="border-y border-zinc-200 bg-white px-6 py-14 text-center"><CalendarDays aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">No timestamped fixtures for this view</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{filter === 'all' ? 'Import a permitted fixture and odds feed, or choose another date.' : 'This competition group has no imported matches on the selected day. Try All tracked or another date.'}</p></div>
}

function MatchdayLoading({ label }: { label: string }) {
  return <div className="flex min-h-48 items-center justify-center gap-2 border border-zinc-200 bg-white text-sm text-zinc-500"><RefreshCw aria-hidden="true" className="animate-spin" size={17} />{label}</div>
}

function MatchdayError({ message }: { message: string }) {
  return <div className="flex items-start gap-3 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={18} /><div><p className="font-bold">Matchday data unavailable</p><p className="mt-1">{message}</p></div></div>
}
