import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Matchday, MatchdayEventDetail } from '../types'
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
          is_stale: false,
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
    expect(screen.getAllByText('Beacon Bet')).toHaveLength(2)
    expect(screen.getByText('Overround')).toBeInTheDocument()
    expect(screen.getByText('Margin')).toBeInTheDocument()
    expect(screen.getByText('Fair probability')).toBeInTheDocument()
    expect(screen.getByText('39.7%')).toBeInTheDocument()
    expect(screen.getByText(/Team form unavailable/)).toBeInTheDocument()
    expect(screen.getByText('Player markets remain research-only')).toBeInTheDocument()
    expect(screen.getByText('No verified builder value')).toBeInTheDocument()
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
  })
})
