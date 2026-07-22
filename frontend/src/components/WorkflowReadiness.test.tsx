import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData, ReadinessCounts } from '../types'
import { WorkflowReadiness } from './WorkflowReadiness'

afterEach(cleanup)

const zero: ReadinessCounts = { events: 1, odds_snapshots: 4, final_results: 20, model_versions: 1, predictions: 0, non_demo_calibrated_evaluations: 0, signals: 0, signal_backtests: 0, bookmaker_tax_mappings: 0, bookmaker_constraints: 0, intelligence_records: 0 }
const dashboard: DashboardData = { status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false }, events: [], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], readiness: zero, resource_errors: {} }

describe('WorkflowReadiness', () => {
  it('shows exact missing signal layers and routes to the responsible tab', () => {
    const navigate = vi.fn()
    render(<WorkflowReadiness dashboard={dashboard} view="opportunities" onNavigate={navigate} />)
    expect(screen.getByText('3 prerequisites missing')).toBeInTheDocument()
    expect(screen.getByText('Run a qualifying evaluation')).toBeInTheDocument()
    expect(screen.getByText('Persist pre-kickoff predictions')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Go to Run a qualifying evaluation'))
    expect(navigate).toHaveBeenCalledWith('models')
  })

  it('marks a workflow ready only when every stored count is positive', () => {
    render(<WorkflowReadiness dashboard={{ ...dashboard, readiness: { ...zero, predictions: 2 } }} view="builder" onNavigate={() => undefined} />)
    expect(screen.getByText('Workflow prerequisites available')).toBeInTheDocument()
  })
})
