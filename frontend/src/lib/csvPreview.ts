export type CsvKind = 'odds' | 'results' | 'availability'

export interface CsvPreviewError {
  row?: number
  field: string
  message: string
}

export interface CsvPreview {
  headers: string[]
  rows: string[][]
  totalRows: number
  errors: CsvPreviewError[]
}

const expectedHeaders: Record<CsvKind, readonly string[]> = {
  odds: ['provider_event_key', 'competition', 'country', 'season', 'kickoff_at', 'home_team', 'away_team', 'bookmaker', 'market_type', 'selection_code', 'selection_name', 'decimal_odds', 'observed_at', 'line', 'source_updated_at', 'period', 'currency', 'settlement_rule_key', 'is_closing'],
  results: ['provider_event_key', 'competition', 'country', 'season', 'kickoff_at', 'home_team', 'away_team', 'home_goals', 'away_goals', 'settled_at', 'observed_at', 'source_updated_at'],
  availability: ['published_at', 'observed_at', 'provider_player_key', 'team_id', 'event_id', 'status', 'reason', 'evidence_class', 'confidence', 'effective_from', 'effective_to'],
}

export function parseCsvPreview(text: string, kind: CsvKind): CsvPreview {
  const records = parseCsv(text.replace(/^\uFEFF/, ''))
  const headerRecord = records[0]
  if (!headerRecord || headerRecord.every((value) => !value.trim())) {
    return { headers: [], rows: [], totalRows: 0, errors: [{ field: 'file', message: 'CSV file is empty' }] }
  }
  const headers = headerRecord.map((value) => value.trim())
  const data = records.slice(1).filter((row) => row.some((value) => value.trim()))
  const errors: CsvPreviewError[] = []
  const required = expectedHeaders[kind]
  const missing = required.filter((header) => !headers.includes(header))
  const unknown = headers.filter((header) => !required.includes(header))
  if (missing.length) errors.push({ field: 'header', message: `Missing columns: ${missing.join(', ')}` })
  if (unknown.length) errors.push({ field: 'header', message: `Unknown columns: ${unknown.join(', ')}` })
  if (!data.length) errors.push({ field: 'file', message: 'CSV contains no data rows' })
  data.forEach((row, index) => {
    if (row.length !== headers.length) errors.push({ row: index + 2, field: 'row', message: `Expected ${headers.length} columns but found ${row.length}` })
  })
  return { headers, rows: data.slice(0, 5), totalRows: data.length, errors: errors.slice(0, 100) }
}

export async function previewCsvFile(file: File, kind: CsvKind, onProgress?: (percent: number) => void): Promise<CsvPreview> {
  if (file.size > 5 * 1024 * 1024) return { headers: [], rows: [], totalRows: 0, errors: [{ field: 'file', message: 'CSV exceeds the 5 MiB preview limit' }] }
  const text = await readFile(file, onProgress)
  return parseCsvPreview(text, kind)
}

function readFile(file: File, onProgress?: (percent: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onprogress = (event) => { if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100)) }
    reader.onerror = () => reject(new Error('Unable to read CSV file'))
    reader.onload = () => { onProgress?.(100); resolve(typeof reader.result === 'string' ? reader.result : '') }
    reader.readAsText(file, 'utf-8')
  })
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') { value += '"'; index += 1 }
      else if (character === '"') quoted = false
      else value += character
    } else if (character === '"') quoted = true
    else if (character === ',') { row.push(value); value = '' }
    else if (character === '\n') { row.push(value.replace(/\r$/, '')); rows.push(row); row = []; value = '' }
    else value += character
  }
  if (value.length || row.length) { row.push(value.replace(/\r$/, '')); rows.push(row) }
  return rows
}
