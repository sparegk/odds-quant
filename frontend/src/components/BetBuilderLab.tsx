import { AlertTriangle, Beaker, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { createBuilderQuote, loadBuilderQuotes, loadPredictions } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type { BetBuilderQuote, EventSummary, ModelOutput } from '../types'

const LEG_OPTIONS = [
  { key: 'MATCH_RESULT|HOME|', label: 'Home win', market_type: 'MATCH_RESULT', selection: 'HOME', line: null },
  { key: 'MATCH_RESULT|DRAW|', label: 'Draw', market_type: 'MATCH_RESULT', selection: 'DRAW', line: null },
  { key: 'MATCH_RESULT|AWAY|', label: 'Away win', market_type: 'MATCH_RESULT', selection: 'AWAY', line: null },
  { key: 'TOTAL_GOALS|OVER|2.5', label: 'Over 2.5 goals', market_type: 'TOTAL_GOALS', selection: 'OVER', line: 2.5 },
  { key: 'TOTAL_GOALS|UNDER|2.5', label: 'Under 2.5 goals', market_type: 'TOTAL_GOALS', selection: 'UNDER', line: 2.5 },
  { key: 'BOTH_TEAMS_TO_SCORE|YES|', label: 'Both teams to score', market_type: 'BOTH_TEAMS_TO_SCORE', selection: 'YES', line: null },
  { key: 'BOTH_TEAMS_TO_SCORE|NO|', label: 'Both teams not to score', market_type: 'BOTH_TEAMS_TO_SCORE', selection: 'NO', line: null },
  { key: 'TEAM_TOTAL_HOME|OVER|1.5', label: 'Home over 1.5 goals', market_type: 'TEAM_TOTAL_HOME', selection: 'OVER', line: 1.5 },
  { key: 'TEAM_TOTAL_AWAY|OVER|1.5', label: 'Away over 1.5 goals', market_type: 'TEAM_TOTAL_AWAY', selection: 'OVER', line: 1.5 },
] as const

interface BetBuilderLabProps {
  events: EventSummary[]
  selectedEventId: number | null
  onSelectEvent: (eventId: number) => void
}

export function BetBuilderLab({ events, selectedEventId, onSelectEvent }: BetBuilderLabProps) {
  const [predictions, setPredictions] = useState<ModelOutput[]>([])
  const [quotes, setQuotes] = useState<BetBuilderQuote[]>([])
  const [legKeys, setLegKeys] = useState<string[]>([LEG_OPTIONS[0].key, LEG_OPTIONS[3].key])
  const [offeredOdds, setOfferedOdds] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (selectedEventId === null) return
    let active = true
    void Promise.resolve()
      .then(() => {
        if (active) {
          setLoading(true)
          setError(null)
        }
        return Promise.all([loadPredictions(selectedEventId), loadBuilderQuotes(selectedEventId)])
      })
      .then(([loadedPredictions, loadedQuotes]) => {
        if (active) {
          setPredictions(loadedPredictions)
          setQuotes(loadedQuotes)
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setPredictions([])
          setQuotes([])
          setError(caught instanceof Error ? caught.message : 'Unable to load bet-builder evidence')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [selectedEventId])

  const latestPrediction = predictions[0]
  const normalizedLegs = useMemo(
    () => legKeys.map((key) => LEG_OPTIONS.find((option) => option.key === key)).filter((leg) => leg !== undefined),
    [legKeys],
  )
  const duplicateLegs = new Set(legKeys).size !== legKeys.length

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (selectedEventId === null || latestPrediction === undefined || duplicateLegs) return
    setSubmitting(true)
    setError(null)
    const quotedAt = new Date().toISOString()
    const price = offeredOdds.trim() ? Number(offeredOdds) : null
    try {
      const quote = await createBuilderQuote({
        event_id: selectedEventId,
        prediction_output_id: latestPrediction.id,
        legs: normalizedLegs.map(({ market_type, selection, line }) => ({ market_type, selection, line })),
        ...(price === null ? {} : {
          offered_odds: price,
          offered_odds_source: 'Dashboard manual observation',
          offered_odds_observed_at: quotedAt,
        }),
        quoted_at: quotedAt,
      })
      setQuotes((current) => [quote, ...current.filter((item) => item.id !== quote.id)])
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create bet-builder quote')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-7">
      <div>
        <p className="text-xs font-bold uppercase text-emerald-700">Stored scoreline distribution</p>
        <h2 className="mt-1 text-lg font-bold">Correlated outcome laboratory</h2>
      </div>

      <label className="block max-w-xl">
        <span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Event</span>
        <select className="h-10 w-full rounded-[5px] border border-zinc-300 bg-white px-3 text-sm font-medium" value={selectedEventId ?? ''} onChange={(event) => onSelectEvent(Number(event.target.value))}>
          {events.map((event) => <option key={event.id} value={event.id}>{event.home_team} vs {event.away_team} - {event.competition}</option>)}
        </select>
      </label>

      {loading ? <div className="flex items-center gap-2 border-y border-zinc-200 bg-white px-5 py-10 text-sm text-zinc-500"><RefreshCw className="animate-spin" size={17} />Loading stored predictions and quotes</div> : null}
      {error ? <div className="flex gap-3 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950"><AlertTriangle className="shrink-0" size={19} /><p>{error}</p></div> : null}

      {!loading && !latestPrediction ? (
        <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center">
          <Beaker className="mx-auto text-zinc-400" size={28} />
          <h3 className="mt-3 font-bold">No stored pre-kickoff prediction</h3>
          <p className="mx-auto mt-2 max-w-lg text-sm text-zinc-500">Train a model and persist an event prediction before evaluating correlated legs.</p>
        </div>
      ) : null}

      {!loading && latestPrediction ? (
        <form className="border border-zinc-200 bg-white" onSubmit={(event) => void submit(event)}>
          <div className="border-b border-zinc-200 p-5">
            <p className="font-semibold">Prediction #{latestPrediction.id} / {latestPrediction.model_version}</p>
            <p className="mt-1 text-xs text-zinc-500">Inputs as of {formatDateTime(latestPrediction.inputs_as_of)} / {latestPrediction.sample_size} training matches / {humanizeCode(latestPrediction.evidence_class)}</p>
          </div>
          <div className="space-y-3 p-5">
            {legKeys.map((key, index) => (
              <div key={index} className="flex gap-2">
                <label className="flex-1">
                  <span className="sr-only">Leg {index + 1}</span>
                  <select className="h-10 w-full rounded-[5px] border border-zinc-300 bg-white px-3 text-sm" value={key} onChange={(event) => setLegKeys((current) => current.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}>
                    {LEG_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                </label>
                <button aria-label={`Remove leg ${index + 1}`} className="grid h-10 w-10 place-items-center border border-zinc-300 text-zinc-600 disabled:opacity-40" disabled={legKeys.length <= 2} onClick={() => setLegKeys((current) => current.filter((_, itemIndex) => itemIndex !== index))} type="button"><Trash2 size={16} /></button>
              </div>
            ))}
            {duplicateLegs ? <p className="text-sm font-semibold text-rose-700">Each leg must be unique.</p> : null}
            <button className="flex items-center gap-2 text-sm font-semibold text-emerald-700 disabled:opacity-40" disabled={legKeys.length >= 4} onClick={() => setLegKeys((current) => [...current, LEG_OPTIONS[5].key])} type="button"><Plus size={16} />Add leg</button>
            <label className="block max-w-xs">
              <span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Optional offered decimal odds</span>
              <input className="h-10 w-full rounded-[5px] border border-zinc-300 px-3 text-sm" min="1.01" step="0.01" type="number" value={offeredOdds} onChange={(event) => setOfferedOdds(event.target.value)} />
              <span className="mt-1 block text-xs text-zinc-500">Manual prices are timestamped at submission.</span>
            </label>
          </div>
          <div className="border-t border-zinc-200 bg-zinc-50 px-5 py-4">
            <button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={submitting || duplicateLegs} type="submit">{submitting ? 'Evaluating…' : 'Evaluate combination'}</button>
          </div>
        </form>
      ) : null}

      <div className="space-y-4">
        {quotes.map((quote) => <BuilderQuoteCard key={quote.id} quote={quote} />)}
        {!loading && latestPrediction && !quotes.length ? <p className="border-y border-zinc-200 bg-white px-5 py-8 text-center text-sm text-zinc-500">No combinations have been stored for this event.</p> : null}
      </div>
    </div>
  )
}

export function BuilderQuoteCard({ quote }: { quote: BetBuilderQuote }) {
  return (
    <article className="border border-zinc-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 p-5">
        <div><h3 className="font-bold">{quote.legs.map((leg) => `${humanizeCode(leg.selection)} ${humanizeCode(leg.market_type)}`).join(' + ')}</h3><p className="mt-1 text-xs text-zinc-500">Quote #{quote.id} / fingerprint {quote.fingerprint.slice(0, 12)} / {quote.is_demo ? 'DEMO MODEL' : 'NON-DEMO MODEL'}</p></div>
        <span className="rounded-[4px] border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-bold text-sky-800">SCORELINE SUM</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5">
        <QuoteMetric label="Joint probability" value={`${(quote.joint_probability * 100).toFixed(1)}%`} />
        <QuoteMetric label="95% lower bound" value={`${(quote.lower_joint_probability * 100).toFixed(1)}%`} />
        <QuoteMetric label="Independent product" value={`${(quote.independent_product * 100).toFixed(1)}%`} />
        <QuoteMetric label="Fair odds" value={quote.fair_odds.toFixed(2)} />
        <QuoteMetric label="Lower-bound EV" value={quote.lower_expected_value === null ? '—' : `${quote.lower_expected_value >= 0 ? '+' : ''}${(quote.lower_expected_value * 100).toFixed(1)}%`} />
      </div>
      <div className="border-t border-zinc-200 px-5 py-4 text-xs leading-5 text-zinc-600">
        <p>Model {quote.model_version} / feature {quote.feature_version} / inputs {formatDateTime(quote.inputs_as_of)}</p>
        {quote.warnings.map((warning) => <p key={warning} className="mt-1 text-amber-800">{warning}</p>)}
      </div>
    </article>
  )
}

function QuoteMetric({ label, value }: { label: string; value: string }) {
  return <div className="border-r border-b border-zinc-200 p-4 md:border-b-0"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono text-lg font-bold">{value}</p></div>
}
