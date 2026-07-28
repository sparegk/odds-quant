import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Matchday, MatchdayCompetition, MatchdayEventDetail } from '../types'
import { MatchdayResearch } from './MatchdayResearch'

const apiMocks = vi.hoisted(() => ({
  loadMatchday: vi.fn(),
  loadMatchdayEvent: vi.fn(),
}))

vi.mock('../api/client', () => apiMocks)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const event = {
  id: 42,
  provider_event_key: 'epl-42',
  competition: 'Premier League',
  country: 'England',
  season: '2026/27',
  home_team: 'Northbridge FC',
  away_team: 'Riverside Athletic',
  kickoff_at: '2026-07-21T18:00:00Z',
  status: 'scheduled',
  is_demo: false,
  latest_odds_at: '2026-07-21T12:00:00Z',
}

const schedule: Matchday = {
  date: '2026-07-21',
  timezone: 'Europe/Athens',
  local_start: '2026-07-20T21:00:00Z',
  local_end: '2026-07-21T21:00:00Z',
  as_of: '2026-07-21T12:05:00Z',
  total_events: 1,
  competitions: [
    {
      competition_id: 3,
      name: 'Premier League',
      country: 'England',
      season: '2026/27',
      group_key: 'premier-league',
      group_label: 'Premier League',
      priority: 20,
      is_featured: true,
      events: [
        {
          event,
          market_count: 1,
          bookmaker_count: 2,
          latest_prediction_at: '2026-07-21T11:00:00Z',
          qualified_signal_count: 0,
        },
      ],
    },
  ],
  data_note: 'Only imported, timestamped fixtures are shown.',
}

const baseCompetition = schedule.competitions[0] as MatchdayCompetition

const scheduleWithUnpricedFirst: Matchday = {
  ...schedule,
  total_events: 2,
  competitions: [
    {
      ...baseCompetition,
      events: [
        {
          event: {
            ...event,
            id: 41,
            provider_event_key: 'epl-41',
            home_team: 'Unpriced FC',
          },
          market_count: 0,
          bookmaker_count: 0,
          latest_prediction_at: null,
          qualified_signal_count: 0,
        },
        ...baseCompetition.events,
      ],
    },
  ],
}

const detail: MatchdayEventDetail = {
  event,
  competition_group: 'premier-league',
  competition_group_label: 'Premier League',
  as_of: '2026-07-21T12:05:00Z',
  team_form: [
    {
      team_id: 1,
      team: 'Northbridge FC',
      sample_size: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      goals_for: 0,
      goals_against: 0,
      clean_sheets: 0,
      points_per_game: null,
      results: [],
      warnings: ['No timestamp-valid prior final results are stored for this team.'],
    },
    {
      team_id: 2,
      team: 'Riverside Athletic',
      sample_size: 2,
      wins: 0,
      draws: 1,
      losses: 1,
      goals_for: 1,
      goals_against: 3,
      clean_sheets: 0,
      points_per_game: 0.5,
      results: [],
      warnings: [],
    },
  ],
  markets: [
    {
      market_id: 7,
      market_type: 'MATCH_RESULT',
      line: null,
      period: 'FULL_TIME',
      currency: 'EUR',
      settlement_rule_key: 'standard_90_minutes',
      snapshots: [
        {
          snapshot_id: 9,
          bookmaker_id: 4,
          bookmaker: 'Beacon Bet',
          provider: 'Licensed feed',
          observed_at: '2026-07-21T12:00:00Z',
          source_updated_at: '2026-07-21T11:59:00Z',
          is_closing: false,
          is_demo: false,
          source_label: 'LICENSED API',
          freshness_seconds: 300,
          is_stale: true,
          overround: 1.05,
          bookmaker_margin: 0.05,
          prices: [
            {
              selection_code: 'HOME', selection_name: 'Home win', decimal_odds: 2.4,
              raw_implied_probability: 0.4167, proportional_fair_probability: 0.3968,
              proportional_fair_odds: 2.52, power_fair_probability: 0.4,
              power_fair_odds: 2.5,
            },
          ],
        },
      ],
      best_prices: [
        {
          selection_code: 'HOME',
          selection_name: 'Home win',
          bookmaker: 'Beacon Bet',
          decimal_odds: 2.4,
          observed_at: '2026-07-21T12:00:00Z',
          freshness_seconds: 300,
        },
      ],
    },
  ],
  latest_prediction: {
    id: 11,
    event_id: 42,
    model_version_id: 5,
    model_version: 'poisson-v1',
    predicted_at: '2026-07-21T11:00:00Z',
    inputs_as_of: '2026-07-21T11:00:00Z',
    evidence_class: 'team_baseline',
    lineup_snapshot_ids: [],
    home_lambda: 1.5,
    away_lambda: 0.9,
    sample_size: 500,
    score_matrix: [],
    derived_probabilities: {},
    predictions: [
      {
        id: 13,
        market_id: 7,
        market_type: 'MATCH_RESULT',
        line: null,
        selection_id: 17,
        selection_code: 'HOME',
        selection_name: 'Home win',
        probability: 0.52,
        lower_probability: 0.47,
        upper_probability: 0.57,
        fair_odds: 1.92,
      },
    ],
  },
  signals: [],
  builder_quotes: [],
  suggestions: [
    {
      rank: 1,
      source_kind: 'single',
      source_id: 21,
      bookmaker_code: 'novibet',
      bookmaker: 'Novibet',
      market_type: 'DOUBLE_CHANCE',
      selection_code: 'HOME_OR_DRAW',
      selection_name: 'Home or draw',
      line: null,
      legs: [],
      offered_odds: 1.8,
      model_probability: 0.68,
      lower_probability: 0.62,
      market_fair_probability: 0.56,
      expected_value: 0.224,
      lower_expected_value: 0.116,
      confidence: 0.8,
      conservative_score: 0.0928,
      price_observed_at: '2026-07-21T12:03:00Z',
      generated_at: '2026-07-21T12:05:00Z',
      reasons: ['Calibrated lower bound clears the market price.'],
      risks: ['Prices can move before placement.'],
    },
  ],
  selected_bookmakers: ['allwyn', 'novibet'],
  bookmaker_options: [
    {
      code: 'allwyn', name: 'Allwyn / Pamestoixima', selected: true,
      has_current_prices: false, offered_market_types: [],
    },
    {
      code: 'novibet', name: 'Novibet', selected: true,
      has_current_prices: true, offered_market_types: ['DOUBLE_CHANCE', 'MATCH_RESULT'],
    },
  ],
  suggestion_market_statuses: [
    { code: 'match_result', label: '1X2', status: 'price_only', reason: 'Price stored.' },
    { code: 'double_chance', label: 'Double chance (1X / X2 / 12)', status: 'available', reason: 'Qualified suggestion.' },
    { code: 'goals', label: 'Goals / BTTS / team totals', status: 'blocked', reason: 'No fresh price.' },
    { code: 'builder', label: 'Bet builder', status: 'blocked', reason: 'No exact quote.' },
    { code: 'corners', label: 'Corners', status: 'price_only', reason: 'Price only; target unvalidated.' },
    { code: 'shots', label: 'Shots', status: 'blocked', reason: 'Target unvalidated.' },
    { code: 'shots_on_target', label: 'Shots on target', status: 'blocked', reason: 'Target unvalidated.' },
    { code: 'player_props', label: 'Player props', status: 'blocked', reason: 'Target unvalidated.' },
  ],
  availability_audit: [
    {
      code: 'match_result',
      label: '1X2',
      status: 'available',
      present_records: 1,
      research_only: false,
      evidence: ['1 compatible market stored.', '1 fresh bookmaker snapshot retained.'],
      blockers: [],
      unlock_requirements: ['Keep the exact price fresh.'],
    },
    {
      code: 'goals',
      label: 'Goals, BTTS & team totals',
      status: 'blocked',
      present_records: 0,
      research_only: true,
      evidence: ['0 compatible markets stored.'],
      blockers: ['No fresh goals price is stored.'],
      unlock_requirements: ['Import timestamped totals, BTTS, or team-total prices.'],
    },
    {
      code: 'lineups',
      label: 'Expected & confirmed lineups',
      status: 'partial',
      present_records: 1,
      research_only: true,
      evidence: ['1 point-in-time fallback starter retained.'],
      blockers: ['One team still lacks a complete position-valid XI.'],
      unlock_requirements: ['Provide 11 position-valid starters for both teams.'],
    },
    {
      code: 'player_props',
      label: 'Player props',
      status: 'blocked',
      present_records: 0,
      research_only: true,
      evidence: ['0 timestamp-valid player targets stored.'],
      blockers: ['Player targets and settlement are not independently validated.'],
      unlock_requirements: ['Pass independent target and settlement validation.'],
    },
    {
      code: 'player_evidence',
      label: 'Player performance evidence',
      status: 'blocked',
      present_records: 0,
      research_only: true,
      evidence: ['0 timestamp-valid player performance records stored.'],
      blockers: ['Position-adjusted player history is unavailable.'],
      unlock_requirements: ['Import timestamp-valid, position-appropriate player history.'],
    },
  ],
  stored_lineups: [],
  lineup_projections: [
    {
      event_id: 42,
      team_id: 1,
      team: 'Northbridge FC',
      status: 'projected',
      scenario_kind: 'availability_weighted',
      formation: '4-3-3',
      as_of: '2026-07-21T12:05:00Z',
      feature_version: 'expected-lineup-v1',
      input_fingerprint: '1234567890abcdef',
      historical_matches: 5,
      confidence: 0.68,
      uncertainty: 0.32,
      starters: [
        {
          player_id: 101,
          player: 'Projected Keeper',
          position: 'GK',
          role: null,
          start_probability: 0.86,
          recent_appearances: 5,
          recent_starts: 5,
          recent_minutes: 450,
          availability_status: 'available',
        },
      ],
      alternates: [],
      warnings: ['Projection remains provisional until the official lineup is published.'],
    },
  ],
  lineup_research: {
    status: 'available',
    title: 'Lineup scenarios available',
    available_records: 11,
    reasons: ['Fallback projections remain separate from confirmed lineups.'],
  },
  player_research: {
    status: 'blocked',
    title: 'Player markets remain research-only',
    available_records: 0,
    reasons: ['Player-level targets and settlement rules have not been independently validated.'],
  },
  builder_value: {
    status: 'blocked',
    title: 'No verified builder value',
    available_records: 0,
    reasons: ['A likely combination is not automatically value.'],
  },
  bookmaker_guidance: 'There is no universal best bookmaker for a match.',
  evidence_note: 'High probability is not the same as a betting edge.',
}

describe('MatchdayResearch', () => {
  it('opens the first fixture with stored bookmaker odds', async () => {
    apiMocks.loadMatchday.mockResolvedValue(scheduleWithUnpricedFirst)
    apiMocks.loadMatchdayEvent.mockResolvedValue(detail)
    const selectEvent = vi.fn()

    render(<MatchdayResearch onSelectEvent={selectEvent} />)

    await waitFor(() => {
      expect(apiMocks.loadMatchdayEvent).toHaveBeenCalledWith(42, ['allwyn', 'novibet'])
    })
    expect(selectEvent).toHaveBeenCalledWith(42)
    expect(apiMocks.loadMatchdayEvent).not.toHaveBeenCalledWith(41, expect.anything())
    const blockedFixture = screen.getByRole('button', { name: /Unpriced FC/ })
    expect(within(blockedFixture).getByText('Prices blocked')).toBeInTheDocument()
    expect(within(blockedFixture).getByText('Model blocked')).toHaveAttribute('title', expect.stringContaining('team-history'))
    const readyFixture = screen.getByRole('button', { name: /Northbridge FC/ })
    expect(within(readyFixture).getByText('Model ready')).toHaveAttribute('title', expect.stringContaining('Latest cutoff-safe prediction'))
    expect(within(readyFixture).getByText('No qualified value')).toBeInTheDocument()
  })

  it('shows filtered ranked suggestions, app coverage, and fail-closed markets', async () => {
    apiMocks.loadMatchday.mockResolvedValue(schedule)
    apiMocks.loadMatchdayEvent.mockResolvedValue(detail)
    const selectEvent = vi.fn()

    render(<MatchdayResearch onSelectEvent={selectEvent} />)

    expect(await screen.findByRole('heading', { name: /Northbridge FC vs Riverside Athletic/ })).toBeInTheDocument()
    expect(screen.getByText('Home or draw')).toBeInTheDocument()
    expect(screen.getByText(/Novibet @ 1.80/)).toBeInTheDocument()
    expect(screen.getByText('62.0%')).toBeInTheDocument()
    expect(screen.getByText('Double chance (1X / X2 / 12)')).toBeInTheDocument()
    expect(screen.getByText('Shots on target')).toBeInTheDocument()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Beacon Bet')).toHaveLength(3)
    expect(screen.getByText('Overround')).toBeInTheDocument()
    expect(screen.getByText('Margin')).toBeInTheDocument()
    expect(screen.getByText('Fair probability')).toBeInTheDocument()
    expect(screen.getAllByText('39.7%')).toHaveLength(2)
    expect(screen.getByText(/Team form unavailable/)).toBeInTheDocument()
    expect(screen.getByText('Expected versus confirmed lineups')).toBeInTheDocument()
    expect(screen.getByText('Projected Keeper')).toBeInTheDocument()
    expect(screen.getByText('68.0% confidence')).toBeInTheDocument()
    expect(screen.getByText('32.0% uncertainty')).toBeInTheDocument()
    expect(screen.getByText('Player markets remain research-only')).toBeInTheDocument()
    expect(screen.getByText('No verified builder value')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Availability evidence explorer' })).toBeInTheDocument()
    expect(screen.getAllByTestId('availability-audit-item')).toHaveLength(5)
    expect(screen.getByText('Unavailable does not mean invisible.', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('No fresh goals price is stored.')).toBeVisible()
    expect(screen.getAllByText('Import timestamped totals, BTTS, or team-total prices.')).toHaveLength(2)
    expect(screen.getByText('1 point-in-time fallback starter retained.')).toBeVisible()
    expect(screen.getByText('Research-only prices:')).toBeVisible()
    expect(screen.getAllByText('Evidence kept:', { exact: false }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Evidence still visible:', { exact: false }).length).toBeGreaterThan(0)
    expect(selectEvent).toHaveBeenCalledWith(42)
    await waitFor(() => {
      expect(apiMocks.loadMatchdayEvent).toHaveBeenCalledWith(42, ['allwyn', 'novibet'])
    })

    fireEvent.click(screen.getByRole('button', { name: 'Novibet' }))
    await waitFor(() => {
      expect(apiMocks.loadMatchdayEvent).toHaveBeenLastCalledWith(42, ['novibet'])
    })

    fireEvent.click(screen.getByRole('button', { name: 'Champions League' }))
    expect(screen.getByText('No timestamped fixtures for this view')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try next day' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show all tracked' }))
    expect(screen.queryByText('No timestamped fixtures for this view')).not.toBeInTheDocument()
  })

  it('retries a failed matchday without losing the selected date', async () => {
    apiMocks.loadMatchday.mockRejectedValueOnce(new Error('Temporary upstream failure')).mockResolvedValueOnce(schedule)
    apiMocks.loadMatchdayEvent.mockResolvedValue(detail)

    render(<MatchdayResearch onSelectEvent={() => undefined} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Temporary upstream failure')
    expect(screen.getByText('Your selected date and filters are preserved.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry this matchday' }))
    expect(await screen.findByRole('heading', { name: /Northbridge FC vs Riverside Athletic/ })).toBeInTheDocument()
    expect(apiMocks.loadMatchday).toHaveBeenCalledTimes(2)
  })
})
