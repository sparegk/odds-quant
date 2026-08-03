import { describe, expect, it } from 'vitest'

import { parseCsvPreview } from './csvPreview'

describe('parseCsvPreview', () => {
  it('previews quoted odds rows with the exact atomic schema', () => {
    const header = 'provider_event_key,competition,country,season,kickoff_at,home_team,away_team,bookmaker,market_type,selection_code,selection_name,decimal_odds,observed_at,line,source_updated_at,period,currency,settlement_rule_key,is_closing'
    const preview = parseCsvPreview(`${header}\ne1,"League, One",GB,2026,2026-08-10T18:00:00Z,A,B,Book,moneyline_3way,HOME,A,2.1,2026-08-04T10:00:00Z,,2026-08-04T10:00:00Z,full_time,EUR,standard,false`, 'odds')
    expect(preview.errors).toEqual([])
    expect(preview.totalRows).toBe(1)
    expect(preview.rows[0]?.[1]).toBe('League, One')
  })

  it('reports missing, unknown, and malformed columns before upload', () => {
    const preview = parseCsvPreview('provider_event_key,unexpected\ne1,value,extra', 'results')
    expect(preview.errors.map((error) => error.field)).toEqual(['header', 'header', 'row'])
    expect(preview.errors[0]?.message).toContain('Missing columns')
  })

  it('rejects an empty CSV preview', () => {
    expect(parseCsvPreview('', 'availability').errors[0]?.message).toBe('CSV file is empty')
  })
})
