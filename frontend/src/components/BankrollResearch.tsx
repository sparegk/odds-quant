import { AlertTriangle, CircleDollarSign } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { simulateBankroll } from '../api/client'
import type { BankrollSimulation, SignalBacktest } from '../types'

export function BankrollResearch({ backtests }: { backtests: SignalBacktest[] }) {
  const [runId, setRunId] = useState(backtests[0]?.id.toString() ?? '')
  const [strategy, setStrategy] = useState<'flat' | 'percentage' | 'fractional_kelly'>('flat')
  const [initialBankroll, setInitialBankroll] = useState('1000')
  const [simulation, setSimulation] = useState<BankrollSimulation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!backtests.length) {
    return (
      <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center">
        <CircleDollarSign className="mx-auto text-zinc-400" size={30} />
        <h2 className="mt-3 font-bold">No settled signal backtest</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-zinc-500">Run a timestamp-valid signal backtest before researching bankroll paths. Calibration runs alone do not contain betting returns.</p>
      </div>
    )
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setSimulation(await simulateBankroll({
        backtest_run_id: Number(runId),
        strategy,
        initial_bankroll: Number(initialBankroll),
      }))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to simulate bankroll')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-7">
      <div><p className="text-xs font-bold uppercase text-emerald-700">Settled replay only</p><h2 className="mt-1 text-lg font-bold">Bankroll research simulator</h2></div>
      <form className="grid gap-4 border border-zinc-200 bg-white p-5 md:grid-cols-3" onSubmit={(event) => void submit(event)}>
        <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Signal backtest</span><select className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={runId} onChange={(event) => setRunId(event.target.value)}>{backtests.map((run) => <option key={run.id} value={run.id}>Run #{run.id} / {run.model_version} / {run.observations.length} bets</option>)}</select></label>
        <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Strategy</span><select className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={strategy} onChange={(event) => setStrategy(event.target.value as typeof strategy)}><option value="flat">Flat stake</option><option value="percentage">Percentage stake</option><option value="fractional_kelly">Capped fractional Kelly</option></select></label>
        <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Initial research bankroll</span><input className="h-10 w-full border border-zinc-300 px-3 text-sm" min="1" step="1" type="number" value={initialBankroll} onChange={(event) => setInitialBankroll(event.target.value)} /></label>
        <button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 md:col-span-3 md:justify-self-start" disabled={loading} type="submit">{loading ? 'Simulating…' : 'Simulate stored sequence'}</button>
      </form>
      {error ? <div className="flex gap-3 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950"><AlertTriangle size={19} /><p>{error}</p></div> : null}
      {simulation ? <BankrollResult simulation={simulation} /> : null}
      <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">Kelly is disabled implicitly when the stored lower probability bound has no positive edge. Every strategy is capped by per-bet and daily exposure limits.</div>
    </div>
  )
}

export function BankrollResult({ simulation }: { simulation: BankrollSimulation }) {
  return (
    <section className="border border-zinc-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 p-5"><div><h3 className="font-bold">{simulation.strategy.replaceAll('_', ' ')} replay</h3><p className="mt-1 text-xs text-zinc-500">Simulation {simulation.simulation_fingerprint.slice(0, 12)} / {simulation.is_demo ? 'DEMO DATA' : 'NON-DEMO DATA'}</p></div><span className="rounded-[4px] border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">RESEARCH ONLY</span></div>
      <div className="grid grid-cols-2 md:grid-cols-5">
        <ResultMetric label="Final bankroll" value={simulation.final_bankroll.toFixed(2)} />
        <ResultMetric label="Net profit" value={signed(simulation.net_profit)} />
        <ResultMetric label="ROI on stakes" value={`${(simulation.roi * 100).toFixed(1)}%`} />
        <ResultMetric label="Maximum drawdown" value={simulation.maximum_drawdown.toFixed(2)} />
        <ResultMetric label="Bets placed" value={simulation.bets_placed.toString()} />
      </div>
      <div className="border-t border-zinc-200 px-5 py-4 text-xs leading-5">{simulation.warnings.map((warning) => <p key={warning} className="mt-1 text-amber-800">{warning}</p>)}</div>
    </section>
  )
}

function ResultMetric({ label, value }: { label: string; value: string }) {
  return <div className="border-r border-b border-zinc-200 p-4 md:border-b-0"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono text-lg font-bold">{value}</p></div>
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
}
