import { useEffect, useMemo, useState } from 'react'
import { Download, Search, SlidersHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'

export interface DesktopColumn<Row> {
  id: string
  label: string
  value: (row: Row) => string | number
  render?: (row: Row) => ReactNode
  align?: 'left' | 'right'
  defaultVisible?: boolean
}

export function DesktopDataTable<Row>({ ariaLabel, columns, filename, rowKey, rows }: { ariaLabel: string; columns: DesktopColumn<Row>[]; filename: string; rowKey: (row: Row) => string | number; rows: Row[] }) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [sortId, setSortId] = useState(columns[0]?.id ?? '')
  const [descending, setDescending] = useState(false)
  const [pageSize, setPageSize] = useState(10)
  const [page, setPage] = useState(1)
  const [visibleIds, setVisibleIds] = useState(() => new Set(columns.filter((column) => column.defaultVisible !== false).map((column) => column.id)))
  const visible = columns.filter((column) => visibleIds.has(column.id))
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 150)
    return () => window.clearTimeout(timer)
  }, [query])
  const processed = useMemo(() => {
    const normalized = debouncedQuery.trim().toLowerCase()
    const filtered = normalized ? rows.filter((row) => columns.some((column) => String(column.value(row)).toLowerCase().includes(normalized))) : rows
    const sortColumn = columns.find((column) => column.id === sortId)
    if (!sortColumn) return filtered
    return [...filtered].sort((left, right) => compare(sortColumn.value(left), sortColumn.value(right)) * (descending ? -1 : 1))
  }, [columns, debouncedQuery, descending, rows, sortId])
  const pages = Math.max(1, Math.ceil(processed.length / pageSize))
  const currentPage = Math.min(page, pages)
  const displayed = processed.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const csv = toCsv(visible, processed)
  const changeQuery = (value: string) => { setQuery(value); setPage(1) }
  const toggleColumn = (id: string) => setVisibleIds((current) => { const next = new Set(current); if (next.has(id) && next.size > 1) next.delete(id); else next.add(id); return next })

  return <div className="border-y border-zinc-200 bg-white">
    <div className="flex items-end gap-3 border-b border-zinc-200 bg-zinc-50 p-3" aria-label={`${ariaLabel} controls`}>
      <label className="min-w-64 flex-1"><span className="mb-1 block text-[10px] font-bold uppercase text-zinc-500">Search rows</span><span className="relative block"><Search aria-hidden="true" className="absolute left-3 top-2.5 text-zinc-400" size={15} /><input aria-label={`${ariaLabel} search`} className="h-9 w-full border border-zinc-300 bg-white pl-9 pr-3 text-xs" value={query} onChange={(event) => changeQuery(event.target.value)} /></span></label>
      <label><span className="mb-1 block text-[10px] font-bold uppercase text-zinc-500">Sort by</span><select aria-label={`${ariaLabel} sort column`} className="h-9 border border-zinc-300 bg-white px-2 text-xs" value={sortId} onChange={(event) => { setSortId(event.target.value); setPage(1) }}>{columns.map((column) => <option key={column.id} value={column.id}>{column.label}</option>)}</select></label>
      <button aria-label={`${ariaLabel} sort direction`} className="h-9 border border-zinc-300 bg-white px-3 text-xs font-bold" onClick={() => setDescending((value) => !value)} type="button">{descending ? 'Descending' : 'Ascending'}</button>
      <label><span className="mb-1 block text-[10px] font-bold uppercase text-zinc-500">Rows</span><select aria-label={`${ariaLabel} rows per page`} className="h-9 border border-zinc-300 bg-white px-2 text-xs" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1) }}><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option></select></label>
      <details className="relative"><summary className="flex h-9 cursor-pointer list-none items-center gap-2 border border-zinc-300 bg-white px-3 text-xs font-bold"><SlidersHorizontal aria-hidden="true" size={14} />Columns</summary><div className="absolute right-0 z-10 mt-1 grid min-w-56 gap-2 border border-zinc-300 bg-white p-3 shadow-lg">{columns.map((column) => <label className="flex items-center gap-2 text-xs" key={column.id}><input checked={visibleIds.has(column.id)} type="checkbox" onChange={() => toggleColumn(column.id)} />{column.label}</label>)}</div></details>
      <a className="inline-flex h-9 items-center gap-2 border border-zinc-300 bg-white px-3 text-xs font-bold" download={filename} href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}><Download aria-hidden="true" size={14} />Export CSV</a>
    </div>
    <div className="overflow-x-auto"><table aria-label={ariaLabel} className="w-full min-w-[980px] border-collapse text-left text-sm"><thead className="bg-zinc-50 text-xs font-semibold uppercase text-zinc-500"><tr>{visible.map((column) => <th className={`px-4 py-3 ${column.align === 'right' ? 'text-right' : ''}`} key={column.id}>{column.label}</th>)}</tr></thead><tbody>{displayed.map((row) => <tr className="border-t border-zinc-100" key={rowKey(row)}>{visible.map((column) => <td className={`px-4 py-3 ${column.align === 'right' ? 'text-right' : ''}`} key={column.id}>{column.render ? column.render(row) : String(column.value(row))}</td>)}</tr>)}</tbody></table></div>
    <div className="flex items-center justify-between border-t border-zinc-200 px-3 py-2 text-xs text-zinc-600"><p>{processed.length} matching row{processed.length === 1 ? '' : 's'} · page {currentPage} of {pages}</p><div className="flex gap-2"><button className="border border-zinc-300 px-3 py-1 font-bold disabled:opacity-40" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))} type="button">Previous</button><button className="border border-zinc-300 px-3 py-1 font-bold disabled:opacity-40" disabled={currentPage === pages} onClick={() => setPage((value) => Math.min(pages, value + 1))} type="button">Next</button></div></div>
  </div>
}

function compare(left: string | number, right: string | number): number { return typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right), undefined, { numeric: true }) }
function toCsv<Row>(columns: DesktopColumn<Row>[], rows: Row[]): string { return [columns.map((column) => csvCell(column.label)).join(','), ...rows.map((row) => columns.map((column) => csvCell(column.value(row))).join(','))].join('\n') }
function csvCell(value: string | number): string { const text = String(value); return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text }
