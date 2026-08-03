import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Upload } from 'lucide-react'

import { uploadCsv } from '../api/client'
import { previewCsvFile } from '../lib/csvPreview'
import type { CsvKind, CsvPreview } from '../lib/csvPreview'
import type { ImportUploadResult } from '../types'

interface Props {
  adminKey: string
  kind: CsvKind
  title: string
  detail: string
  onChanged?: () => Promise<void> | void
}

export function CsvImportPanel({ adminKey, kind, title, detail, onChanged }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [sourceKey, setSourceKey] = useState('')
  const [providerSlug, setProviderSlug] = useState('')
  const [providerName, setProviderName] = useState('')
  const [preview, setPreview] = useState<CsvPreview | null>(null)
  const [result, setResult] = useState<ImportUploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [previewing, setPreviewing] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const chooseFile = async (selected: File | null) => {
    setFile(selected); setPreview(null); setResult(null); setError(null); setProgress(0)
    if (!selected) return
    setPreviewing(true)
    try { setPreview(await previewCsvFile(selected, kind, setProgress)) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Preview failed') }
    finally { setPreviewing(false) }
  }
  const submit = async () => {
    if (!file || !preview || preview.errors.length) return
    setSubmitting(true); setProgress(65); setError(null); setResult(null)
    try {
      setResult(await uploadCsv(kind, file, { adminKey: adminKey || undefined, sourceKey, providerSlug, providerName }))
      setProgress(100)
      await onChanged?.()
    } catch (caught) { setProgress(0); setError(caught instanceof Error ? caught.message : 'Upload failed') }
    finally { setSubmitting(false) }
  }
  const availabilityReady = kind !== 'availability' || Boolean(sourceKey && providerSlug && providerName)
  const preflightReady = Boolean(preview && !preview.errors.length)
  const stage = previewing ? 'Reading file' : submitting ? 'Atomic server validation' : result ? 'Completed' : preflightReady ? 'Preflight passed' : 'Preflight blocked'

  return <article className="border border-zinc-200 bg-white p-5">
    <Upload aria-hidden="true" className="text-emerald-700" size={22} />
    <h3 className="mt-3 font-bold">{title}</h3>
    <p className="mt-1 min-h-16 text-sm leading-6 text-zinc-500">{detail}</p>
    <label className="mt-4 block"><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">CSV file</span><input accept=".csv,text/csv" aria-label={`${title} CSV file`} className="block w-full text-xs" type="file" onChange={(event) => void chooseFile(event.target.files?.[0] ?? null)} /></label>
    {file ? <div className="mt-3" aria-label={`${title} import progress`}><div className="flex justify-between text-[10px] font-bold uppercase text-zinc-500"><span>{stage}</span><span>{progress}%</span></div><div className="mt-1 h-1.5 bg-zinc-100"><div className={`h-full ${preview?.errors.length || error ? 'bg-rose-500' : 'bg-emerald-600'}`} style={{ width: `${progress}%` }} /></div></div> : null}
    {preview ? <CsvPreviewPanel preview={preview} /> : null}
    {kind === 'availability' ? <div className="mt-4 grid gap-3"><TextInput label="Source key" value={sourceKey} onChange={setSourceKey} /><TextInput label="Provider slug" value={providerSlug} onChange={setProviderSlug} /><TextInput label="Provider name" value={providerName} onChange={setProviderName} /></div> : null}
    <button className="mt-5 rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-40" disabled={!file || !preflightReady || !availabilityReady || submitting || previewing} onClick={() => void submit()} type="button">{submitting ? 'Uploading…' : `Import ${kind}`}</button>
    {result ? <div className="mt-4 flex gap-2 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status"><CheckCircle2 aria-hidden="true" className="shrink-0" size={18} /><div><p className="font-bold">Job #{result.job_id} {result.status}</p><p className="text-xs">{result.rows_imported}/{result.rows_received} rows imported atomically.</p></div></div> : null}
    {error ? <div className="mt-4 flex gap-2 border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} /><span>{error}</span></div> : null}
  </article>
}

function CsvPreviewPanel({ preview }: { preview: CsvPreview }) {
  if (preview.errors.length) return <div className="mt-3 border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900" role="alert"><p className="font-bold">Preflight found {preview.errors.length} issue{preview.errors.length === 1 ? '' : 's'}</p>{preview.errors.map((issue, index) => <p className="mt-1" key={`${issue.field}-${issue.row ?? 0}-${index}`}>{issue.row ? `Row ${issue.row} / ` : ''}{issue.field}: {issue.message}</p>)}</div>
  const visibleHeaders = preview.headers.slice(0, 5)
  return <div className="mt-3 border border-emerald-200 bg-emerald-50/40 p-3"><div className="flex items-center justify-between text-xs"><p className="font-bold text-emerald-900">Preflight passed</p><p className="text-emerald-800">{preview.totalRows} data row{preview.totalRows === 1 ? '' : 's'}</p></div><div className="mt-2 overflow-x-auto"><table className="w-full text-left text-[10px]"><thead><tr>{visibleHeaders.map((header) => <th className="border-b border-emerald-200 px-1 py-1 font-bold" key={header}>{header}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 3).map((row, rowIndex) => <tr key={rowIndex}>{row.slice(0, 5).map((value, columnIndex) => <td className="max-w-24 truncate px-1 py-1" key={columnIndex} title={value}>{value || '—'}</td>)}</tr>)}</tbody></table></div><p className="mt-2 text-[10px] text-zinc-500">Showing up to 3 rows and 5 columns. Server validation remains authoritative and atomic.</p></div>
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label><span className="mb-1 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} className="h-9 w-full border border-zinc-300 px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} /></label>
}
