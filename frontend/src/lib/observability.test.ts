import { describe, expect, it } from 'vitest'

import { safeRoute } from './observability'

describe('privacy-safe observability', () => {
  it('drops queries and normalizes numeric resource identifiers', () => {
    expect(safeRoute('/matches/1842?admin_key=secret&note=private')).toBe('/matches/:id')
    expect(safeRoute('/api/v1/models/12/evaluate?cutoff=private')).toBe('/api/v1/models/:id/evaluate')
  })

  it('bounds route values sent to telemetry', () => {
    expect(safeRoute('/' + 'a'.repeat(300))).toHaveLength(160)
  })
})
