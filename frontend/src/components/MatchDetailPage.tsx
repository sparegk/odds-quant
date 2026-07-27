import { Beaker, GitCompareArrows, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { loadMatchdayEvent } from '../api/client'
import type { EventSummary, MatchdayBookmakerCode, MatchdayEventDetail } from '../types'
import { MatchDetail } from './MatchdayResearch'

type BookmakerMode = 'both' | MatchdayBookmakerCode

interface MatchDetailPageProps {
  events: EventSummary[]
  selectedEventId: number | null
  onSelectEvent: (eventId: number) => void
  onOpenBuilder: () => void
  onOpenComparison: () => void
}

export function MatchDetailPage({
  events,
  selectedEventId,
  onSelectEvent,
  onOpenBuilder,
  onOpenComparison,
}: MatchDetailPageProps) {
  const [bookmakerMode, setBookmakerMode] = useState<BookmakerMode>('both')
  const [detail, setDetail] = useState<MatchdayEventDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadVersion, setReloadVersion] = useState(0)
  const bookmakers = useMemo<MatchdayBookmakerCode[]>(
    () => bookmakerMode === 'both' ? ['allwyn', 'novibet'] : [bookmakerMode],
    [bookmakerMode],
  )

  useEffect(() => {
    if (selectedEventId === null) return
    let active = true
    void Promise.resolve()
      .then(() => {
        if (active) {
          setLoading(true)
          setError(null)
        }
        return loadMatchdayEvent(selectedEventId, bookmakers)
      })
      .then((loaded) => {
        if (active) setDetail(loaded)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setDetail(null)
        setError(caught instanceof Error ? caught.message : 'Unable to load match research')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [bookmakers, reloadVersion, selectedEventId])

  return (
    <div className='space-y-6'>
      <section className='border border-zinc-200 bg-white'>
        <div className='flex flex-wrap items-end justify-between gap-4 p-5'>
          <label className='min-w-0 flex-1 sm:min-w-[320px]'>
            <span className='mb-1.5 block text-xs font-semibold uppercase text-zinc-500'>Match</span>
            <select
              aria-label='Match'
              className='h-10 w-full border border-zinc-300 bg-white px-3 text-sm font-medium'
              onChange={(event) => onSelectEvent(Number(event.target.value))}
              value={selectedEventId ?? ''}
            >
              {events.map((event) => <option key={event.id} value={event.id}>{event.home_team} vs {event.away_team} - {event.competition}</option>)}
            </select>
          </label>
          <div className='flex flex-wrap gap-2'>
            <button className='flex h-10 items-center gap-2 border border-zinc-300 px-3 text-xs font-bold hover:bg-zinc-50' onClick={onOpenComparison} type='button'>
              <GitCompareArrows aria-hidden='true' size={15} />Compare all prices
            </button>
            <button className='flex h-10 items-center gap-2 bg-zinc-900 px-3 text-xs font-bold text-white' onClick={onOpenBuilder} type='button'>
              <Beaker aria-hidden='true' size={15} />Open builder lab
            </button>
          </div>
        </div>
        <div className='flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 bg-zinc-50 px-5 py-3'>
          <div>
            <p className='text-xs font-bold uppercase text-zinc-700'>Price filter</p>
            <p className='mt-0.5 text-xs text-zinc-500'>Suggestions require an exact stored price from the selected apps.</p>
          </div>
          <div aria-label='Price filter' className='flex' role='group'>
            {([
              ['both', 'Both apps'],
              ['allwyn', 'Allwyn'],
              ['novibet', 'Novibet'],
            ] as const).map(([value, label]) => (
              <button
                aria-pressed={bookmakerMode === value}
                className={`border px-3 py-2 text-xs font-bold first:rounded-l last:rounded-r ${bookmakerMode === value ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-zinc-300 bg-white text-zinc-600'}`}
                key={value}
                onClick={() => setBookmakerMode(value)}
                type='button'
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {loading ? <div className='flex items-center justify-center gap-2 border-y border-zinc-200 bg-white px-5 py-12 text-sm text-zinc-500'><RefreshCw aria-hidden='true' className='animate-spin' size={17} />Loading the complete match record</div> : null}
      {error ? (
        <div className='border border-rose-200 bg-rose-50 p-5 text-sm text-rose-950' role='alert'>
          <h2 className='font-bold'>Match research could not be loaded</h2>
          <p className='mt-1'>{error}</p>
          <p className='mt-2 text-rose-800'>Your selected match and bookmaker filter are preserved.</p>
          <button className='mt-3 bg-rose-800 px-3 py-2 font-semibold text-white' onClick={() => setReloadVersion((version) => version + 1)} type='button'>Retry match research</button>
        </div>
      ) : null}
      {!loading && !error && selectedEventId !== null && detail ? <MatchDetail detail={detail} /> : null}
      {!loading && !error && !detail ? <div className='border-y border-zinc-200 bg-white px-5 py-12 text-center'><h2 className='font-bold'>No match selected</h2><p className='mt-2 text-sm text-zinc-500'>{events.length ? 'Choose a tracked match above to inspect its complete research record.' : 'No tracked matches are available yet. Import a permitted fixture feed in Data operations first.'}</p></div> : null}
    </div>
  )
}
