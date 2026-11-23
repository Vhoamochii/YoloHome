import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis
} from 'recharts'
import { SensorPoint } from '../services/api'

// Chart ink on the dark chart surface (bg-neutral-900).
const SURFACE = '#171717'
const INK_PRIMARY = '#f0efec'
const INK_MUTED = '#898781'
const GRID = 'rgba(255, 255, 255, 0.08)'
const AXIS = 'rgba(255, 255, 255, 0.16)'

// The board publishes every 30 s; a longer silence means it was offline, so the line breaks there.
const GAP_MS = 5 * 60 * 1000

type Field = 'temperature' | 'humidity'
interface Point {
  t: number
  v: number | null
}

function toSeries(history: SensorPoint[], field: Field): Point[] {
  const out: Point[] = []
  let prev = 0
  for (const p of history) {
    const value = p[field]
    if (!p.recorded_at || value == null) continue
    const t = new Date(p.recorded_at).getTime()
    if (prev && t - prev > GAP_MS) out.push({ t: prev + 1, v: null })
    out.push({ t, v: Math.round(value * 10) / 10 })
    prev = t
  }
  return out
}

/** Evenly spaced whole-number ticks with a little headroom around the data. */
function niceTicks(points: Point[]) {
  const values = points.flatMap((p) => (p.v == null ? [] : [p.v]))
  let lo = Math.floor(Math.min(...values)) - 1
  let hi = Math.ceil(Math.max(...values)) + 1
  const step = hi - lo <= 6 ? 1 : hi - lo <= 12 ? 2 : 5
  lo = Math.floor(lo / step) * step
  hi = Math.ceil(hi / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi; v += step) ticks.push(v)
  return ticks
}

function hhmm(t: number) {
  return new Date(t).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

function ChartTooltip({ active, payload, label, unit, color }: TooltipProps<number, string> & { unit: string; color: string }) {
  const value = payload?.[0]?.value
  if (!active || value == null) return null
  return (
    <div className="rounded-lg border border-white/10 bg-neutral-900/95 px-3 py-2 shadow-xl">
      <div className="flex items-center gap-2">
        <span className="h-0.5 w-3 rounded-full" style={{ background: color }} />
        <span className="text-sm font-semibold" style={{ color: INK_PRIMARY }}>
          {value.toFixed(1)}
          {unit}
        </span>
      </div>
      <div className="mt-0.5 text-xs" style={{ color: INK_MUTED }}>
        {new Date(Number(label)).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
      </div>
    </div>
  )
}

interface SensorChartProps {
  title: string
  unit: string
  color: string
  field: Field
  history: SensorPoint[]
}

/** One series over the last 24 h: temperature and humidity get a chart each (different scales, never one dual axis). */
export default function SensorChart({ title, unit, color, field, history }: SensorChartProps) {
  const points = useMemo(() => toSeries(history, field), [history, field])
  const last = [...points].reverse().find((p) => p.v != null)
  const enough = points.filter((p) => p.v != null).length >= 2
  const ticks = useMemo(() => (enough ? niceTicks(points) : []), [points, enough])

  return (
    <section className="rounded-2xl border border-white/10 bg-neutral-900/85 p-4 backdrop-blur-md">
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold text-white">{title} · 24 giờ qua</h2>
        <span className="text-xs" style={{ color: INK_MUTED }}>
          {unit}
        </span>
      </div>

      {enough && last ? (
        <div
          className="mt-3 h-44"
          role="img"
          aria-label={`Biểu đồ ${title.toLowerCase()} 24 giờ qua, giá trị mới nhất ${last.v?.toFixed(1)}${unit}`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 44, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={['dataMin', 'dataMax']}
                tickFormatter={hhmm}
                minTickGap={48}
                tick={{ fill: INK_MUTED, fontSize: 11 }}
                axisLine={{ stroke: AXIS }}
                tickLine={false}
              />
              <YAxis
                domain={[ticks[0], ticks[ticks.length - 1]]}
                ticks={ticks}
                width={32}
                tick={{ fill: INK_MUTED, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<ChartTooltip unit={unit} color={color} />}
                cursor={{ stroke: 'rgba(255, 255, 255, 0.35)', strokeWidth: 1 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 4, fill: color, stroke: SURFACE, strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
              <ReferenceDot
                x={last.t}
                y={last.v as number}
                r={4}
                fill={color}
                stroke={SURFACE}
                strokeWidth={2}
                label={{ value: `${last.v?.toFixed(1)}${unit}`, position: 'right', fill: INK_PRIMARY, fontSize: 11 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-xs text-white/60">Chưa đủ dữ liệu trong 24 giờ qua để vẽ biểu đồ.</p>
      )}
    </section>
  )
}
