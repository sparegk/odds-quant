import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { BankrollSimulation } from '../types'
import { BankrollResult, BankrollStressComparison } from './BankrollResearch'

const simulation: BankrollSimulation = {
  backtest_run_id: 4,
  backtest_fingerprint: 'backtest1234567890',
  simulation_fingerprint: 'simulation1234567890',
  strategy: 'fractional_kelly',
  initial_bankroll: 1000,
  final_bankroll: 1042.5,
  total_staked: 180,
  net_profit: 42.5,
  roi: 0.2361,
  maximum_drawdown: 25,
  maximum_drawdown_fraction: 0.024,
  bets_placed: 12,
  bets_skipped: 3,
  is_demo: true,
  warnings: ['This is a deterministic research replay, not a forecast of future returns.'],
  points: [],
}

describe('BankrollResult', () => {
  it('labels demo research and displays return and drawdown separately', () => {
    render(<BankrollResult simulation={simulation} />)

    expect(screen.getByText(/fractional kelly replay/i)).toBeInTheDocument()
    expect(screen.getByText(/DEMO DATA/)).toBeInTheDocument()
    expect(screen.getByText('1042.50')).toBeInTheDocument()
    expect(screen.getByText('+42.50')).toBeInTheDocument()
    expect(screen.getByText('23.6%')).toBeInTheDocument()
    expect(screen.getByText('25.00')).toBeInTheDocument()
    expect(screen.getByText('RESEARCH ONLY')).toBeInTheDocument()
    expect(screen.getByText(/not a forecast of future returns/)).toBeInTheDocument()
  })

  it('compares stored strategy paths without presenting forecast uncertainty', () => {
    render(<BankrollStressComparison simulations={[simulation, { ...simulation, simulation_fingerprint: 'flat-simulation', strategy: 'flat', final_bankroll: 1010, maximum_drawdown_fraction: 0.05, bets_placed: 10, bets_skipped: 5 }]} />)

    expect(screen.getByRole('heading', { name: 'Stored parameter comparisons' })).toBeInTheDocument()
    expect(screen.getByText('fractional kelly')).toBeInTheDocument()
    expect(screen.getByText('flat')).toBeInTheDocument()
    expect(screen.getByText('Final-bankroll spread').parentElement).toHaveTextContent('32.50')
    expect(screen.getByText('Worst drawdown').parentElement).toHaveTextContent('5.0%')
    expect(screen.getByText(/not forecast uncertainty/)).toBeInTheDocument()
  })
})
