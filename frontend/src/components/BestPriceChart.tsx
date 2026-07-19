import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { MarketComparison } from '../types'

interface BestPriceChartProps {
  market: MarketComparison
}

export function BestPriceChart({ market }: BestPriceChartProps) {
  const data = market.best_prices.map((price) => ({
    selection: price.selection_name,
    odds: price.decimal_odds,
    bookmaker: price.bookmaker,
  }))
  return (
    <div className="h-64 w-full" aria-label="Best available odds chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="#e4e4e7" vertical={false} />
          <XAxis dataKey="selection" tick={{ fill: '#52525b', fontSize: 12 }} />
          <YAxis domain={[0, 'auto']} tick={{ fill: '#71717a', fontSize: 12 }} />
          <Tooltip
            formatter={(value) => [Number(value).toFixed(2), 'Best odds']}
            contentStyle={{ border: '1px solid #d4d4d8', borderRadius: 6, boxShadow: 'none' }}
          />
          <Bar dataKey="odds" fill="#247a57" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
