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
import { useEffect, useMemo, useRef, useState } from 'react'

import { loadMatchday, loadMatchdayEvent } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import { useResearchPreference } from '../lib/researchPreferences'
import { nextGoodMatchdayDate } from '../lib/matchdays'
import type {
  AvailabilityAuditItem,
  BetBuilderQuote,
  ExpectedLineupScenario,
  EventSummary,
  Matchday,
  MatchdayBookmakerCode,
  MatchdayCompetition,
  MatchdayEventDetail,
  MatchSuggestion,
  MarketComparison,
  ResearchGate,
  SnapshotComparison,
  StoredLineup,
  TeamForm,
} from '../types'
import { BookmakerSettings, CompetitionCard } from './MatchdaySchedule'
import type { BookmakerMode } from './MatchdaySchedule'

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

const isDatePreference = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)
const isCompetitionPreference = (value: string) => competitionFilters.some((item) => item.key === value)
const isBookmakerPreference = (value: string) => ['both', 'allwyn', 'novibet'].includes(value)

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

function percentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function signedPercentage(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

function signedPoints(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)} pp`
}

function findFirstEvent(competitions: MatchdayCompetition[]): number | null {
  const events = competitions.flatMap((competition) => competition.events)
  return (
    events.find((item) => item.market_count > 0 && item.bookmaker_count > 0)?.event.id ??
    events.find((item) => item.market_count > 0)?.event.id ??
    events[0]?.event.id ??
    null
  )
}

export function MatchdayResearch({
  events = [],
  onSelectEvent,
}: {
  events?: EventSummary[]
  onSelectEvent: (eventId: number) => void
}) {
  const [timezone] = useResearchPreference('matchday_timezone', Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Athens')
  const nextGoodDate = useMemo(
    () => nextGoodMatchdayDate(events, timezone),
    [events, timezone],
  )
  const [date, setDate] = useResearchPreference('matchday_date', nextGoodMatchdayDate(events, timezone) ?? localDateString(new Date()), isDatePreference)
  const [filterPreference, setFilter] = useResearchPreference('matchday_competition', 'all', isCompetitionPreference)
  const filter = filterPreference as (typeof competitionFilters)[number]['key']
  const [schedule, setSchedule] = useState<Matchday | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [detail, setDetail] = useState<MatchdayEventDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [scheduleReload, setScheduleReload] = useState(0)
  const [detailReload, setDetailReload] = useState(0)
  const [bookmakerPreference, setBookmakerMode] = useResearchPreference('matchday_bookmakers', 'both', isBookmakerPreference)
  const recoveredEmptyLanding = useRef(false)
  const bookmakerMode = bookmakerPreference as BookmakerMode
  const selectedBookmakers = useMemo<MatchdayBookmakerCode[]>(
    () => (bookmakerMode === 'both' ? ['allwyn', 'novibet'] : [bookmakerMode]),
    [bookmakerMode],
  )

  useEffect(() => {
    let active = true
    let redirecting = false
    void loadMatchday(date, timezone)
      .then((loaded) => {
        if (!active) return
        const recoveryDate = nextGoodDate ?? loaded.next_event_date
        if (
          !recoveredEmptyLanding.current &&
          loaded.total_events === 0 &&
          recoveryDate &&
          recoveryDate !== date &&
          date <= localDateString(new Date())
        ) {
          recoveredEmptyLanding.current = true
          redirecting = true
          setDate(recoveryDate)
          return
        }
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
        if (active && !redirecting) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [date, nextGoodDate, onSelectEvent, scheduleReload, setDate, timezone])

  useEffect(() => {
    if (selectedEventId === null) {
      return
    }
    let active = true
    void loadMatchdayEvent(selectedEventId, selectedBookmakers)
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
  }, [detailReload, selectedBookmakers, selectedEventId])

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

  const chooseBookmakerMode = (mode: BookmakerMode) => {
    if (mode === bookmakerMode) return
    setBookmakerMode(mode)
    if (selectedEventId !== null) {
      setDetailLoading(true)
      setDetailError(null)
      setDetail(null)
    }
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
            {nextGoodDate ? (
              <button
                className="h-10 border border-emerald-700 bg-emerald-50 px-3 text-xs font-bold text-emerald-800 hover:bg-emerald-100"
                onClick={() => chooseDate(nextGoodDate)}
                type="button"
              >
                Next good matchday
              </button>
            ) : null}
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
        {nextGoodDate ? (
          <div className="border-b border-emerald-200 bg-emerald-50 px-5 py-3 text-xs leading-5 text-emerald-950">
            <strong>Next useful slate: {nextGoodDate}.</strong> This prioritizes the earliest future,
            non-demo featured competition with stored prices.
          </div>
        ) : null}
        <BookmakerSettings mode={bookmakerMode} onChange={chooseBookmakerMode} />
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

      {error ? <MatchdayError actionLabel='Retry this matchday' message={error} onRetry={() => { setLoading(true); setScheduleReload((version) => version + 1) }} /> : null}
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
                {detailError ? <MatchdayError actionLabel='Retry match research' message={detailError} onRetry={() => { setDetailLoading(true); setDetailReload((version) => version + 1) }} /> : null}
                {!detailLoading && detail ? <MatchDetail detail={detail} /> : null}
              </div>
            </div>
          ) : (
            <EmptyMatchday
              filter={filter}
              nextEventDate={schedule.next_event_date}
              onNextDay={() => chooseDate(schedule.next_event_date ?? shiftDate(date, 1))}
              onPreviousDay={schedule.previous_event_date ? () => chooseDate(schedule.previous_event_date!) : null}
              onShowAll={() => setFilter('all')}
              previousEventDate={schedule.previous_event_date}
            />
          )}
          <p className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">
            {schedule.data_note}
          </p>
        </>
      ) : null}
    </div>
  )
}

export function MatchDetail({ detail }: { detail: MatchdayEventDetail }) {
  const bestPrices = detail.markets.flatMap((market) => market.best_prices.map((price) => ({ market, price })))
  const builderQuotes = [...detail.builder_quotes].sort((left, right) => (right.lower_expected_value ?? -1) - (left.lower_expected_value ?? -1))
  const storedSnapshots = detail.markets.flatMap((market) => market.snapshots)
  const onlyStalePrices = storedSnapshots.length > 0 && storedSnapshots.every((snapshot) => snapshot.is_stale)

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
        <BookmakerAvailability detail={detail} />
        <BetRecommendations detail={detail} />
        <AvailabilityExplorer detail={detail} />
        <PredictionEvidence detail={detail} />
        <ModelMarketLab detail={detail} />

        <MarketCoverage detail={detail} />

        <section>
          <DetailHeading eyebrow="Line shopping" title="Best bookmaker by selection" />
          {onlyStalePrices ? (
            <div className="mb-3 border-l-4 border-amber-400 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950" role="status">
              <strong>Research-only prices:</strong> every stored snapshot is stale. The odds remain visible so you can inspect the prior market, but they cannot qualify as a current suggestion.
            </div>
          ) : null}
          {bestPrices.length ? (
            <>
            <div className="overflow-x-auto border-y border-zinc-200">
              <table className="w-full min-w-[580px] text-left text-sm">
                <thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-3 py-2.5">Market</th><th className="px-3 py-2.5">Selection</th><th className="px-3 py-2.5">Bookmaker</th><th className="px-3 py-2.5 text-right">Odds</th></tr></thead>
                <tbody>{bestPrices.map(({ market, price }) => <tr className="border-t border-zinc-100" key={`${market.market_id}-${price.selection_code}`}><td className="px-3 py-2.5">{humanizeCode(market.market_type)}{market.line === null ? '' : ` ${market.line}`}</td><td className="px-3 py-2.5 font-semibold">{price.selection_name}</td><td className="px-3 py-2.5">{price.bookmaker}</td><td className="px-3 py-2.5 text-right font-mono font-bold">{price.decimal_odds.toFixed(2)}</td></tr>)}</tbody>
              </table>
            </div>
            </>
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

        <LineupResearch detail={detail} />

        <section className="grid gap-4 lg:grid-cols-2">
          <ResearchGateCard
            audit={detail.availability_audit.find((item) => item.code === 'player_evidence')}
            gate={detail.player_research}
            icon="players"
          />
          <div>
            <ResearchGateCard
              audit={detail.availability_audit.find((item) => item.code === 'builder')}
              gate={detail.builder_value}
              icon="builder"
            />
            {builderQuotes.length ? <BuilderQuotes quotes={builderQuotes} /> : null}
          </div>
        </section>
      </div>
    </article>
  )
}

function BetRecommendations({ detail }: { detail: MatchdayEventDetail }) {
  const likely = [...(detail.latest_prediction?.predictions ?? [])].sort((left, right) => right.probability - left.probability)
  const watchlist = [...detail.model_market_comparisons]
    .filter((comparison) => comparison.expected_value > 0)
    .sort((left, right) => right.expected_value - left.expected_value)
    .slice(0, 3)
  const blockers = [...new Set(
    detail.suggestion_market_statuses
      .filter((market) => market.status !== 'available')
      .map((market) => `${market.label}: ${market.reason}`),
  )].slice(0, 4)

  return <section aria-label="Bet recommendations">
    <DetailHeading eyebrow="Qualified evidence only" title="Bet recommendations" />
    {detail.suggestions.length ? (
      <div className="space-y-3">
        {detail.suggestions.map((suggestion) => (
          <SuggestionCard key={`${suggestion.source_kind}-${suggestion.source_id}`} suggestion={suggestion} />
        ))}
      </div>
    ) : (
      <div className="space-y-4">
        <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950" role="status">
          <p className="font-bold">No qualified bet recommendation for this match</p>
          <p className="mt-1">The app will only recommend a selection when a calibrated lower probability clears a fresh, exact selected-bookmaker price.</p>
          {blockers.length ? <ul className="mt-2 list-disc pl-5 text-xs">{blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul> : null}
        </div>
        {watchlist.length ? <div>
          <p className="text-xs font-bold uppercase text-sky-700">Research watchlist—not recommendations</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-3">{watchlist.map((comparison) => <div className="border border-sky-200 bg-sky-50 p-3" key={`${comparison.market_id}-${comparison.selection_id}`}><p className="text-xs font-semibold text-zinc-600">{comparison.selection_name} · {comparison.best_bookmaker}</p><p className="mt-1 font-mono font-bold">{comparison.best_odds.toFixed(2)} · raw EV {signedPercentage(comparison.expected_value)}</p><p className="mt-1 text-[11px] leading-4 text-sky-900">{comparison.qualification_blockers[0] ?? 'Qualification gates remain unresolved.'}</p></div>)}</div>
        </div> : null}
        {likely.length ? <div>
          <p className="mb-2 text-xs font-bold uppercase text-zinc-500">Outcome likelihoods—not betting edges</p>
          <div className="grid gap-2 sm:grid-cols-3">{likely.slice(0, 3).map((prediction) => <div className="border border-zinc-200 p-3" key={prediction.id}><p className="text-xs font-semibold text-zinc-500">{prediction.selection_name}</p><p className="mt-2 text-xl font-bold">{percentage(prediction.probability)}</p><p className="mt-1 text-xs text-zinc-500">Fair odds {prediction.fair_odds.toFixed(2)} / lower {percentage(prediction.lower_probability)}</p></div>)}</div>
        </div> : <ResearchEmpty text="No timestamp-valid pre-kickoff model output is stored for this match." />}
      </div>
    )}
    <p className="mt-3 text-xs leading-5 text-zinc-500">{detail.evidence_note}</p>
  </section>
}

function ModelMarketLab({ detail }: { detail: MatchdayEventDetail }) {
  const comparisons = detail.model_market_comparisons
  const calibration = detail.calibration_reliability
  return <section>
    <DetailHeading eyebrow="Transparent arithmetic" title="Model vs market lab" />
    <div className="mb-3 border-l-4 border-sky-500 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-950">
      <strong>Research-only arithmetic.</strong> This joins the stored model interval to fresh,
      exact prices from the selected bookmakers. It does not create a VALUE signal, use a closing
      line, or make a staking recommendation.
    </div>
    <div className={`mb-3 border-l-4 px-3 py-3 text-xs leading-5 ${calibration.status === 'available' ? 'border-emerald-500 bg-emerald-50 text-emerald-950' : 'border-amber-400 bg-amber-50 text-amber-950'}`}>
      <p className="font-bold">Chronological probability calibration reliability</p>
      <dl className="mt-2 grid grid-cols-2 gap-px bg-zinc-200 sm:grid-cols-4">
        <LabMetric label="Calibration status" value={calibration.status === 'available' ? 'Validated before cutoff' : 'Unavailable'} />
        <LabMetric label="Expected calibration error" value={calibration.expected_calibration_error === null ? 'Unavailable' : percentage(calibration.expected_calibration_error)} />
        <LabMetric label="Brier score" value={calibration.brier_score === null ? 'Unavailable' : calibration.brier_score.toFixed(4)} />
        <LabMetric label="Log loss" value={calibration.log_loss === null ? 'Unavailable' : calibration.log_loss.toFixed(4)} />
        <LabMetric label="Calibration sample" value={calibration.sample_size.toLocaleString()} />
        <LabMetric label="Temperature" value={calibration.temperature === null ? 'Unavailable' : calibration.temperature.toFixed(4)} />
        <LabMetric label="Evaluation run" value={calibration.evaluation_run_id === null ? 'Unavailable' : `#${calibration.evaluation_run_id}`} />
        <LabMetric label="Fit through" value={calibration.fit_through === null ? 'Unavailable' : formatDateTime(calibration.fit_through)} />
      </dl>
      <p className="mt-2">Probability reliability only: market-edge evidence included = no; betting-return evidence included = no.</p>
      {calibration.blockers.length > 0 && <ul className="mt-1 list-disc pl-4">{calibration.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>}
    </div>
    {comparisons.length ? (
      <div className="space-y-3">
        {comparisons.map((comparison) => (
          <article className="border border-zinc-200" key={`${comparison.market_id}-${comparison.selection_code}`}>
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 bg-zinc-50 p-3">
              <div>
                <p className="text-xs font-bold uppercase text-zinc-500">
                  {humanizeCode(comparison.market_type)}{comparison.line === null ? '' : ` ${comparison.line}`}
                </p>
                <h4 className="mt-1 font-bold">{comparison.selection_name}</h4>
              </div>
              <div className="text-right">
                <p className="font-mono text-lg font-bold">{comparison.best_odds.toFixed(2)}</p>
                <p className="text-xs text-zinc-500">{comparison.best_bookmaker} / best selected price</p>
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-px bg-zinc-200 sm:grid-cols-4">
              <LabMetric label="Model probability" value={percentage(comparison.model_probability)} />
              <LabMetric label="Market consensus" value={percentage(comparison.market_consensus_probability)} />
              <LabMetric label="Best-price break-even" value={percentage(comparison.best_price_break_even_probability)} />
              <LabMetric label="Model fair odds" value={comparison.model_fair_odds.toFixed(2)} />
              <LabMetric label="Model edge" value={signedPoints(comparison.probability_edge)} />
              <LabMetric label="Conservative edge" value={signedPoints(comparison.conservative_edge)} warning={comparison.conservative_edge <= 0} />
              <LabMetric label="Price edge" value={signedPoints(comparison.price_probability_edge)} />
              <LabMetric label="Conservative price edge" value={signedPoints(comparison.conservative_price_edge)} warning={comparison.conservative_price_edge <= 0} />
              <LabMetric label={`Pre-cost EV/unit @ ${comparison.best_odds.toFixed(2)}`} value={signedPercentage(comparison.expected_value)} />
              <LabMetric label="Lower pre-cost EV/unit" value={signedPercentage(comparison.lower_expected_value)} warning={comparison.lower_expected_value <= 0} />
              <LabMetric label="Net EV/cash unit" value={comparison.cost_adjusted_expected_value === null ? 'Unavailable' : signedPercentage(comparison.cost_adjusted_expected_value)} />
              <LabMetric label="Lower net EV/cash unit" value={comparison.lower_cost_adjusted_expected_value === null ? 'Unavailable' : signedPercentage(comparison.lower_cost_adjusted_expected_value)} warning={comparison.lower_cost_adjusted_expected_value !== null && comparison.lower_cost_adjusted_expected_value <= 0} />
              <LabMetric label="Cost calculation stake" value={comparison.cost_calculation_stake === null ? 'Unavailable' : `${comparison.cost_calculation_stake.toFixed(2)} ${comparison.cost_currency}`} />
              <LabMetric label="Cash outlay after stake costs" value={comparison.cost_calculation_cash_outlay === null ? 'Unavailable' : `${comparison.cost_calculation_cash_outlay.toFixed(2)} ${comparison.cost_currency}`} />
              <LabMetric label="Lower-bound fair odds" value={comparison.lower_fair_odds === null ? 'Unavailable' : comparison.lower_fair_odds.toFixed(2)} />
              <LabMetric label="Model uncertainty width" value={signedPoints(comparison.model_uncertainty_width).replace('+', '')} />
              <LabMetric label="Market range" value={`${percentage(comparison.market_probability_low)}–${percentage(comparison.market_probability_high)}`} />
              <LabMetric label="Book / method spread" value={`${signedPoints(comparison.bookmaker_disagreement).replace('+', '')} / ${signedPoints(comparison.devig_method_spread).replace('+', '')}`} />
              <LabMetric label="Market uncertainty width" value={signedPoints(comparison.market_uncertainty_width).replace('+', '')} />
            </dl>
            <div className="border-t border-zinc-200 p-3">
              <p className="text-xs font-bold uppercase text-zinc-500">Pre-registered de-vig sensitivity</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {comparison.devig_sensitivity.map((item) => <div className="border border-zinc-200 bg-white p-2" key={item.method}>
                  <div className="flex items-center justify-between gap-2"><span className="font-semibold capitalize">{item.method}</span><span className="text-[10px] font-bold uppercase text-zinc-500">{item.frozen_replay_primary ? 'Frozen replay primary' : 'Sensitivity only'}</span></div>
                  <p className="mt-1 font-mono">Consensus {percentage(item.market_consensus_probability)} / edge {signedPoints(item.model_probability_edge)}</p>
                  <p className="text-zinc-600">Conservative edge {signedPoints(item.conservative_probability_edge)} / range {percentage(item.market_probability_low)}-{percentage(item.market_probability_high)}</p>
                </div>)}
              </div>
              <p className={`mt-2 text-xs font-semibold ${comparison.devig_conclusion_stable ? 'text-emerald-800' : 'text-amber-800'}`}>Method conclusion: {comparison.devig_conclusion_stable ? 'stable across proportional and power de-vigging' : 'method-sensitive; edge sign or conservative conclusion changes'}.</p>
              <p className="mt-1 text-xs text-zinc-500">This robustness view cannot rewrite the frozen proportional replay or create a VALUE signal.</p>
            </div>
            <div className="p-3 text-xs leading-5 text-zinc-600">
              <p>{comparison.bookmaker_count} selected bookmaker{comparison.bookmaker_count === 1 ? '' : 's'} included. Best price observed {formatDateTime(comparison.best_price_observed_at)}.</p>
              <p className={comparison.pre_cost_advantage_survives_uncertainty ? 'font-semibold text-emerald-800' : 'font-semibold text-amber-800'}>
                Pre-cost uncertainty test: {comparison.pre_cost_advantage_survives_uncertainty ? 'survives both model and market bounds' : 'does not survive both model and market bounds'}.
              </p>
              <p className={comparison.cost_adjusted_advantage_survives_uncertainty ? 'font-semibold text-emerald-800' : 'font-semibold text-amber-800'}>
                Cost-adjusted uncertainty test: {comparison.cost_adjusted_advantage_survives_uncertainty === null ? 'unavailable until sourced cost evidence is complete and fresh' : comparison.cost_adjusted_advantage_survives_uncertainty ? 'survives the conservative model bound after costs' : 'does not survive the conservative model bound after costs'}.
              </p>
              <p>Settlement: {comparison.settlement_rule_key} / currency: {comparison.cost_currency}. Cost ROI uses the displayed valid rounded stake because fixed fees make results stake-dependent.</p>
              {comparison.cost_evidence_blockers.length > 0 && <ul className="mt-1 list-disc pl-4 text-amber-800">
                {comparison.cost_evidence_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
              </ul>}
              <ul className="mt-1 list-disc pl-4">
                {comparison.qualification_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
              </ul>
            </div>
          </article>
        ))}
      </div>
    ) : (
      <ResearchEmpty text={detail.latest_prediction
        ? 'Comparison blocked: no fresh exact selected-bookmaker price matches the stored prediction.'
        : 'Comparison blocked: no timestamp-valid pre-kickoff model output is stored.'} />
    )}
  </section>
}

function LabMetric({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return <div className="bg-white p-3"><dt className="text-[11px] font-semibold uppercase text-zinc-500">{label}</dt><dd className={`mt-1 font-mono font-bold ${warning ? 'text-amber-700' : 'text-zinc-900'}`}>{value}</dd></div>
}

function PredictionEvidence({ detail }: { detail: MatchdayEventDetail }) {
  const prediction = detail.latest_prediction
  if (!prediction) {
    return <section><DetailHeading eyebrow="Model boundary" title="Prediction evidence layer" /><ResearchEmpty text="No timestamp-valid pre-kickoff model output is stored. Team history, model availability, and cutoff evidence must be inspected before a probability can be shown." /></section>
  }
  const confirmedContext = prediction.evidence_class === 'confirmed_lineup_context_unadjusted'
  return <section>
    <DetailHeading eyebrow="Model boundary" title="Prediction evidence layer" />
    <div className={`border-l-4 p-4 ${confirmedContext ? 'border-sky-500 bg-sky-50' : 'border-zinc-400 bg-zinc-50'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-bold">{confirmedContext ? 'Confirmed lineup context / unadjusted baseline' : humanizeCode(prediction.evidence_class)}</p>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-700">{confirmedContext ? 'Complete confirmed lineup snapshots were available at the cutoff, but player-strength adjustments are not independently validated. Probabilities remain team-baseline values.' : 'This output uses team-level baseline evidence. No expected or confirmed lineup adjustment is included in its probabilities.'}</p>
        </div>
        <span className="border border-zinc-300 bg-white px-2 py-1 text-xs font-bold">{confirmedContext ? 'CONTEXT ONLY' : 'TEAM BASELINE'}</span>
      </div>
      <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
        <PredictionMetric label="Model version" value={prediction.model_version} />
        <PredictionMetric label="Inputs as of" value={formatDateTime(prediction.inputs_as_of)} />
        <PredictionMetric label="Prediction time" value={formatDateTime(prediction.predicted_at)} />
        <PredictionMetric label="Lineup snapshots" value={prediction.lineup_snapshot_ids.length ? prediction.lineup_snapshot_ids.map((id) => `#${id}`).join(', ') : 'None applied'} />
        <PredictionMetric label="Uncertainty" value={`${humanizeCode(prediction.probability_uncertainty.version.replaceAll('-', '_'))} / ${prediction.probability_uncertainty.successful_refits || 'legacy'} refits`} />
        <PredictionMetric label="Calibration" value={prediction.probability_calibration.applied ? `${humanizeCode(prediction.probability_calibration.version.replaceAll('-', '_'))} / T ${prediction.probability_calibration.temperature?.toFixed(3)}` : 'Raw probabilities / no accepted calibrator'} />
        <PredictionMetric label="Feature activation" value={`${humanizeCode(prediction.feature_activation.status)} / ${prediction.feature_activation.probabilities_adjusted ? 'probabilities adjusted' : 'probabilities unchanged'}`} />
      </dl>
      {prediction.feature_activation.blockers.length ? <details className="mt-4 border-t border-zinc-200 pt-3 text-xs text-zinc-600"><summary className="cursor-pointer font-bold text-zinc-800">Player and tactical activation blockers</summary><ul className="mt-2 list-disc space-y-1 pl-5">{prediction.feature_activation.blockers.map((blocker) => <li key={blocker}>{humanizeCode(blocker)}</li>)}</ul><p className="mt-2 font-mono">Gate {prediction.feature_activation.version}</p></details> : null}
    </div>
  </section>
}

function PredictionMetric({ label, value }: { label: string; value: string }) {
  return <div><dt className="font-semibold uppercase text-zinc-500">{label}</dt><dd className="mt-1 font-mono text-zinc-800">{value}</dd></div>
}

function AvailabilityExplorer({ detail }: { detail: MatchdayEventDetail }) {
  const counts = detail.availability_audit.reduce(
    (result, item) => ({ ...result, [item.status]: result[item.status] + 1 }),
    { available: 0, partial: 0, blocked: 0 },
  )

  return (
    <section aria-label="Availability evidence explorer">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <DetailHeading eyebrow="Nothing hidden" title="Availability evidence explorer" />
        <div className="mb-3 flex flex-wrap gap-2 text-[11px] font-bold uppercase">
          <span className="border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-800">
            {counts.available} available
          </span>
          <span className="border border-sky-200 bg-sky-50 px-2 py-1 text-sky-800">
            {counts.partial} partial
          </span>
          <span className="border border-amber-200 bg-amber-50 px-2 py-1 text-amber-800">
            {counts.blocked} blocked
          </span>
        </div>
      </div>
      <p className="mb-3 text-xs leading-5 text-zinc-600">
        Unavailable does not mean invisible. Open evidence is retained below with the exact
        blocker and what must be added before it can qualify.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {detail.availability_audit.map((item) => {
          const available = item.status === 'available'
          const partial = item.status === 'partial'
          return (
            <details
              className={
                available
                  ? 'border border-emerald-200 bg-emerald-50'
                  : partial
                    ? 'border border-sky-200 bg-sky-50'
                    : 'border border-amber-200 bg-amber-50'
              }
              data-testid="availability-audit-item"
              key={item.code}
              open={!available}
            >
              <summary className="cursor-pointer list-none p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold">{item.label}</p>
                    <p className="mt-1 text-xs text-zinc-600">
                      {item.present_records} stored record{item.present_records === 1 ? '' : 's'}
                      {item.research_only ? ' / research-only' : ''}
                    </p>
                  </div>
                  <span
                    className={
                      available
                        ? 'text-[10px] font-bold uppercase text-emerald-700'
                        : partial
                          ? 'text-[10px] font-bold uppercase text-sky-700'
                          : 'text-[10px] font-bold uppercase text-amber-700'
                    }
                  >
                    {item.status}
                  </span>
                </div>
              </summary>
              <div className="space-y-3 border-t border-black/10 px-3 py-3 text-xs leading-5">
                <AuditList label="Evidence retained" items={item.evidence} tone="neutral" />
                <AuditList label="Why it is blocked" items={item.blockers} tone="warning" />
                <AuditList label="What unlocks it" items={item.unlock_requirements} tone="action" />
              </div>
            </details>
          )
        })}
      </div>
    </section>
  )
}

function AuditList({
  label,
  items,
  tone,
}: {
  label: string
  items: string[]
  tone: 'neutral' | 'warning' | 'action'
}) {
  if (!items.length) return null
  return (
    <div>
      <p
        className={
          tone === 'warning'
            ? 'font-bold text-amber-900'
            : tone === 'action'
              ? 'font-bold text-sky-900'
              : 'font-bold text-zinc-700'
        }
      >
        {label}
      </p>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-zinc-700">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}

function BookmakerAvailability({ detail }: { detail: MatchdayEventDetail }) {
  return (
    <section aria-label="Selected bookmaker coverage" className="border border-zinc-200 bg-zinc-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-zinc-600">Active suggestion filter</p>
          <p className="mt-1 text-sm font-semibold">
            {detail.selected_bookmakers.map((code) => code === 'allwyn' ? 'Allwyn' : 'Novibet').join(' + ')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {detail.bookmaker_options.map((option) => (
            <span
              className={`border px-2 py-1 text-xs font-semibold ${
                option.selected && option.has_current_prices
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                  : option.selected
                    ? 'border-amber-300 bg-amber-50 text-amber-800'
                    : 'border-zinc-200 bg-white text-zinc-400'
              }`}
              key={option.code}
            >
              {option.name}: {option.has_current_prices ? `${option.offered_market_types.length} priced markets` : 'no fresh prices'}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

function SuggestionCard({ suggestion }: { suggestion: MatchSuggestion }) {
  return (
    <div className="border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-emerald-700">
            #{suggestion.rank} {suggestion.source_kind === 'builder' ? 'Bet builder' : humanizeCode(suggestion.market_type)}
          </p>
          <p className="mt-1 font-bold">
            {suggestion.selection_name}
            {suggestion.line === null ? '' : ` ${suggestion.line}`}
          </p>
        </div>
        <p className="font-mono font-bold">{suggestion.bookmaker} @ {suggestion.offered_odds.toFixed(2)}</p>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <EvidenceMetric label="Model chance" value={percentage(suggestion.model_probability)} />
        <EvidenceMetric label="Conservative chance" value={percentage(suggestion.lower_probability)} />
        <EvidenceMetric label="Lower pre-cost EV" value={signedPercentage(suggestion.lower_expected_value)} />
        <EvidenceMetric label="Net EV/cash unit" value={signedPercentage(suggestion.net_expected_value)} />
        <EvidenceMetric label="Lower net EV/cash unit" value={signedPercentage(suggestion.lower_net_expected_value)} />
        <EvidenceMetric label="Cost basis" value={`${suggestion.cost_calculation_stake.toFixed(2)} stake / ${suggestion.cost_calculation_cash_outlay.toFixed(2)} ${suggestion.cost_currency} outlay`} />
        <EvidenceMetric
          label="Confidence"
          value={suggestion.confidence === null ? 'Builder interval' : percentage(suggestion.confidence)}
        />
      </div>
      {suggestion.reasons[0] ? <p className="mt-3 text-xs leading-5 text-emerald-950">{suggestion.reasons[0]}</p> : null}
      {suggestion.risks[0] ? <p className="mt-2 flex gap-2 text-xs leading-5 text-amber-900"><ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0" size={14} />{suggestion.risks[0]}</p> : null}
      <p className="mt-2 text-[11px] text-zinc-500">Exact price observed {formatDateTime(suggestion.price_observed_at)}. Recommendation requires complete sourced costs and positive lower net EV at the displayed rounded stake. Recheck the price in the app before placement; no bet is guaranteed.</p>
    </div>
  )
}

function MarketCoverage({ detail }: { detail: MatchdayEventDetail }) {
  return (
    <section>
      <DetailHeading eyebrow="App availability and validation" title="Markets you asked for" />
      <div className="grid gap-2 sm:grid-cols-2">
        {detail.suggestion_market_statuses.map((market) => {
          const available = market.status === 'available'
          const priceOnly = market.status === 'price_only'
          const audit = detail.availability_audit.find((item) => item.code === market.code)
          return (
            <div
              className={`border p-3 ${
                available
                  ? 'border-emerald-200 bg-emerald-50'
                  : priceOnly
                    ? 'border-sky-200 bg-sky-50'
                    : 'border-zinc-200 bg-zinc-50'
              }`}
              key={market.code}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-bold">{market.label}</p>
                <span className={`text-[10px] font-bold uppercase ${available ? 'text-emerald-700' : priceOnly ? 'text-sky-700' : 'text-zinc-500'}`}>
                  {available ? 'Suggestion' : priceOnly ? 'Price only' : 'Unavailable'}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-zinc-600">{market.reason}</p>
              {!available && audit ? (
                <div className="mt-2 border-t border-black/10 pt-2 text-xs leading-5 text-zinc-700">
                  <p><strong>Evidence kept:</strong> {audit.evidence[0] ?? 'No stored evidence.'}</p>
                  <p className="mt-1"><strong>Unlock:</strong> {audit.unlock_requirements[0] ?? 'Additional validated evidence is required.'}</p>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </section>
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
      {form.sample_size === 0 ? <div className="mt-3 border border-amber-200 bg-amber-50 px-3 py-4 text-sm text-amber-900">Team form unavailable ? no timestamp-valid prior final results are stored.</div> : <>
      <div className="mt-3 grid grid-cols-3 border-y border-zinc-100 py-2 text-center text-xs"><div><strong className="block text-base text-emerald-700">{form.wins}</strong>W</div><div><strong className="block text-base">{form.draws}</strong>D</div><div><strong className="block text-base text-rose-700">{form.losses}</strong>L</div></div>
      <p className="mt-3 text-xs text-zinc-500">Goals {form.goals_for}–{form.goals_against} / {form.clean_sheets} clean sheets</p>
      <div className="mt-3 flex flex-wrap gap-1.5">{form.results.map((result) => <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold ${result.outcome === 'W' ? 'bg-emerald-100 text-emerald-800' : result.outcome === 'D' ? 'bg-zinc-200 text-zinc-700' : 'bg-rose-100 text-rose-800'}`} key={result.event_id} title={`${result.venue} vs ${result.opponent}, ${result.goals_for}-${result.goals_against}`}>{result.outcome}</span>)}</div>
      </>}
      {form.warnings.map((warning) => <p className="mt-2 text-xs text-amber-700" key={warning}>{warning}</p>)}
    </div>
  )
}

function LineupResearch({ detail }: { detail: MatchdayEventDetail }) {
  return (
    <section>
      <DetailHeading eyebrow="Availability-aware scenarios" title="Expected versus confirmed lineups" />
      <ResearchGateCard
        audit={detail.availability_audit.find((item) => item.code === 'lineups')}
        gate={detail.lineup_research}
        icon="players"
      />
      {detail.stored_lineups.length ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {detail.stored_lineups.map((lineup) => <StoredLineupCard key={lineup.id} lineup={lineup} />)}
        </div>
      ) : null}
      {detail.lineup_projections.length ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {detail.lineup_projections.map((scenario) => (
            <ProjectedLineupCard
              key={`${scenario.team_id}-${scenario.scenario_kind}`}
              scenario={scenario}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}

function StoredLineupCard({ lineup }: { lineup: StoredLineup }) {
  return (
    <div className="border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase text-emerald-700">{lineup.lineup_type} evidence</p>
          <h4 className="mt-1 font-bold">{lineup.team}</h4>
          <p className="mt-1 text-xs text-zinc-600">{lineup.formation ?? 'Formation unavailable'} / {lineup.provider}</p>
        </div>
        <span className="border border-emerald-300 bg-white px-2 py-1 text-xs font-bold text-emerald-800">
          {percentage(lineup.confidence)} confidence
        </span>
      </div>
      <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {lineup.members.filter((member) => member.starter).map((member) => (
          <div className="flex items-center justify-between border border-emerald-100 bg-white px-2 py-1.5 text-xs" key={member.player_id}>
            <span><strong>{member.position}</strong> {member.player}</span>
            {member.expected_probability === null ? null : <span className="font-mono">{percentage(member.expected_probability)}</span>}
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-zinc-500">Published {formatDateTime(lineup.published_at)}</p>
    </div>
  )
}

function ProjectedLineupCard({ scenario }: { scenario: ExpectedLineupScenario }) {
  const projected = scenario.status === 'projected'
  return (
    <div className={`border p-4 ${projected ? 'border-sky-200 bg-sky-50' : 'border-amber-200 bg-amber-50'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase text-sky-700">
            OddsQuant fallback / {scenario.scenario_kind === 'doubtful_available' ? 'doubtful available' : 'availability weighted'}
          </p>
          <h4 className="mt-1 font-bold">{scenario.team}</h4>
          <p className="mt-1 text-xs text-zinc-600">{scenario.formation} / {scenario.historical_matches} prior matches</p>
        </div>
        <div className="text-right text-xs">
          <p className="font-bold">{percentage(scenario.confidence)} confidence</p>
          <p className="mt-1 text-zinc-500">{percentage(scenario.uncertainty)} uncertainty</p>
        </div>
      </div>
      {scenario.starters.length ? (
        <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
          {scenario.starters.map((member) => (
            <div className="flex items-center justify-between border border-sky-100 bg-white px-2 py-1.5 text-xs" key={member.player_id}>
              <span className="truncate"><strong>{member.position}</strong> {member.player}</span>
              <span className="ml-2 font-mono">{percentage(member.start_probability)}</span>
            </div>
          ))}
        </div>
      ) : <ResearchEmpty text="Not enough timestamp-valid position evidence to project this XI." />}
      {scenario.alternates.length ? <p className="mt-3 text-xs text-zinc-600"><strong>Alternates:</strong> {scenario.alternates.map((member) => `${member.player} ${percentage(member.start_probability)}`).join(', ')}</p> : null}
      {scenario.warnings.map((warning) => <p className="mt-2 text-xs text-amber-800" key={warning}>{warning}</p>)}
      <p className="mt-3 font-mono text-[10px] text-zinc-400" title={scenario.input_fingerprint}>
        {scenario.feature_version} / {scenario.input_fingerprint.slice(0, 12)}
      </p>
    </div>
  )
}

function ResearchGateCard({
  gate,
  icon,
  audit,
}: {
  gate: ResearchGate
  icon: 'players' | 'builder'
  audit?: AvailabilityAuditItem
}) {
  const Icon = icon === 'players' ? Users : Sparkles
  const ready = gate.status === 'available'
  return (
    <div className={`h-full border p-4 ${ready ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}>
      <div className="flex items-start gap-3"><Icon aria-hidden="true" className={ready ? 'text-emerald-700' : 'text-amber-700'} size={20} /><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold">{gate.title}</h3><span className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase ${ready ? 'border-emerald-300 text-emerald-800' : 'border-amber-300 text-amber-800'}`}>{gate.status}</span></div><p className="mt-1 text-xs text-zinc-600">{gate.available_records} relevant stored records</p></div></div>
      <ul className="mt-3 space-y-2 text-xs leading-5 text-zinc-700">{gate.reasons.map((reason) => <li className="flex gap-2" key={reason}>{ready ? <CircleCheck aria-hidden="true" className="mt-0.5 shrink-0 text-emerald-700" size={14} /> : <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-700" size={14} />}{reason}</li>)}</ul>
      {!ready && audit ? (
        <div className="mt-3 border-t border-amber-200 pt-3 text-xs leading-5 text-zinc-700">
          <p><strong>Evidence still visible:</strong> {audit.evidence.join(' ')}</p>
          <p className="mt-1"><strong>Unlock:</strong> {audit.unlock_requirements.join(' ')}</p>
        </div>
      ) : null}
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

function EmptyMatchday({ filter, nextEventDate, onNextDay, onPreviousDay, onShowAll, previousEventDate }: { filter: string; nextEventDate: string | null; onNextDay: () => void; onPreviousDay: (() => void) | null; onShowAll: () => void; previousEventDate: string | null }) {
  return <div className="border-y border-zinc-200 bg-white px-6 py-14 text-center"><CalendarDays aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">No timestamped fixtures for this view</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{filter === 'all' ? 'No permitted fixtures are stored for this date. Jump directly to the nearest stored matchday, or import a fixture and odds feed in Data operations.' : 'This competition group has no imported matches on the selected day. Show all tracked competitions or jump to another stored matchday.'}</p><div className="mt-4 flex flex-wrap justify-center gap-2">{filter !== 'all' ? <button className="border border-zinc-300 px-3 py-2 text-sm font-semibold" onClick={onShowAll} type="button">Show all tracked</button> : null}{onPreviousDay ? <button className="border border-zinc-300 px-3 py-2 text-sm font-semibold" onClick={onPreviousDay} type="button">Previous games: {previousEventDate}</button> : null}<button className="bg-zinc-900 px-3 py-2 text-sm font-semibold text-white" onClick={onNextDay} type="button">{nextEventDate ? `Next games: ${nextEventDate}` : 'Try next day'}</button></div></div>
}

function MatchdayLoading({ label }: { label: string }) {
  return <div className="flex min-h-48 items-center justify-center gap-2 border border-zinc-200 bg-white text-sm text-zinc-500"><RefreshCw aria-hidden="true" className="animate-spin" size={17} />{label}</div>
}

function MatchdayError({ message, actionLabel, onRetry }: { message: string; actionLabel: string; onRetry: () => void }) {
  return <div className="flex items-start gap-3 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={18} /><div><p className="font-bold">Matchday data unavailable</p><p className="mt-1">{message}</p><p className="mt-2 text-rose-800">Your selected date and filters are preserved.</p><button className="mt-3 bg-rose-800 px-3 py-2 font-semibold text-white" onClick={onRetry} type="button">{actionLabel}</button></div></div>
}
