import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTidalis } from '../store'

const tooltipStyle = {
  background: '#0f1c31',
  border: '1px solid #1b2c47',
  borderRadius: 8,
  fontSize: 12,
  color: '#b8c6dd',
}

export default function ForecastPanel() {
  const forecast = useTidalis((s) => s.forecast)

  if (!forecast || forecast.points.length === 0) {
    return <div className="empty-state">NO FORECAST AVAILABLE</div>
  }

  const data = forecast.points.map((p) => ({
    h: `+${p.hours_ahead}h`,
    lower: p.lower_bound,
    band: Math.max(p.upper_bound - p.lower_bound, 0.001),
    pred: p.predicted_value,
  }))

  const first = forecast.points[0]
  const last = forecast.points[forecast.points.length - 1]
  const delta = last.predicted_value - first.predicted_value
  const trend = delta === 0 ? 'flat' : delta > 0 ? 'increasing' : 'decreasing'

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 8, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--muted)' }}>
        {forecast.variable.toUpperCase()} projection · model: {forecast.model_name} ·
        trend: <span style={{ color: delta > 0 ? 'var(--red)' : 'var(--green)' }}>{trend}</span>
        {' '}({(first.predicted_value).toFixed(1)} → {(last.predicted_value).toFixed(1)})
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#14223a" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="h" stroke="#5f7194" fontSize={11} tickLine={false} axisLine={{ stroke: '#1b2c47' }} />
            <YAxis stroke="#5f7194" fontSize={11} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#eaf2ff', fontFamily: 'var(--mono)' }} />
            <Area type="monotone" dataKey="lower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill="rgba(34,211,238,0.13)" isAnimationActive={false} />
            <Line
              type="monotone"
              dataKey="pred"
              stroke="#22d3ee"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}