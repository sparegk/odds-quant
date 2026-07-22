import { useState } from 'react'
import { AlertTriangle, Braces, CheckCircle2, FileJson } from 'lucide-react'

import { importIntelligenceBundle } from '../api/client'
import type { ImportUploadResult } from '../types'

const TEMPLATE = JSON.stringify({
  source_key: 'licensed-provider-export-2026-07-22',
  provider_slug: 'licensed-provider',
  provider_name: 'Licensed Provider',
  is_demo: false,
  players: [{ provider_player_key: 'player-1', name: 'Player Name', position: 'MF' }],
  coaches: [], registrations: [], coach_tenures: [], appearances: [], player_statistics: [],
  availability: [], lineups: [], tactics: [],
}, null, 2)

export function IntelligenceBundleImport({ adminKey }: { adminKey: string }) {
  const [json, setJson] = useState(TEMPLATE)
  const [result, setResult] = useState<ImportUploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const loadFile = async (file: File | undefined) => {
    if (!file) return
    try { setJson(await file.text()); setError(null) } catch { setError('Unable to read the selected JSON file.') }
  }
  const submit = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      const parsed: unknown = JSON.parse(json)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('Bundle must be a JSON object.')
      setResult(await importIntelligenceBundle(parsed as Record<string, unknown>, adminKey || undefined))
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Intelligence import failed') } finally { setBusy(false) }
  }
  return <section className="border border-zinc-200 bg-white"><div className="grid gap-5 border-b border-zinc-200 p-5 lg:grid-cols-[1fr_auto]"><div><div className="flex items-center gap-2"><Braces aria-hidden="true" size={19} /><h3 className="font-bold">Full football-intelligence bundle</h3></div><p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">Import one strict atomic JSON bundle containing any combination of players, coaches, registrations, coach tenures, appearances, position-appropriate statistics, availability, expected or confirmed lineups, and tactical snapshots.</p></div><label className="flex cursor-pointer items-center gap-2 self-start rounded-[5px] border border-zinc-300 px-3 py-2 text-sm font-bold hover:bg-zinc-50"><FileJson aria-hidden="true" size={16} />Load JSON file<input accept="application/json,.json" className="sr-only" type="file" onChange={(event) => void loadFile(event.target.files?.[0])} /></label></div><div className="p-5"><label><span className="mb-2 block text-xs font-semibold uppercase text-zinc-500">Validated bundle JSON</span><textarea aria-label="Intelligence bundle JSON" className="min-h-80 w-full border border-zinc-300 p-3 font-mono text-xs leading-5" spellCheck={false} value={json} onChange={(event) => setJson(event.target.value)} /></label><div className="mt-4 flex flex-wrap items-center gap-3"><button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-40" disabled={busy || !json.trim()} onClick={() => void submit()} type="button">{busy ? 'Validating and importing…' : 'Import intelligence bundle'}</button><button className="rounded-[5px] border border-zinc-300 px-3 py-2 text-sm font-bold" onClick={() => setJson(TEMPLATE)} type="button">Reset template</button><p className="text-xs text-zinc-500">All publication timestamps, identities, lineups, and records are rejected together if any item is invalid.</p></div>{result ? <div className="mt-4 flex gap-2 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status"><CheckCircle2 aria-hidden="true" size={18} /><div><p className="font-bold">Job #{result.job_id} completed</p><p className="text-xs">{result.rows_imported}/{result.rows_received} records imported · fingerprint {result.content_sha256?.slice(0, 16)}</p>{result.created ? <p className="mt-1 text-xs">{Object.entries(result.created).map(([key, count]) => `${key}: ${count}`).join(' · ')}</p> : null}</div></div> : null}{error ? <div className="mt-4 flex gap-2 border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} />{error}</div> : null}</div></section>
}
