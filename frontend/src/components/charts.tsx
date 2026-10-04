import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  AssignmentPassRate,
  CategoryCount,
  MisconceptionCount,
  SubmissionsPerDay,
} from '../api/types'
import { CATEGORY_LABELS, CHART_COLORS, titleCaseTag } from '../lib/ui'

const AXIS = { fontSize: 12, fill: '#64748b' }
const GRID = '#e2e8f0'

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-800">{title}</h3>
      {children}
    </div>
  )
}

export function MisconceptionChart({ data }: { data: MisconceptionCount[] }) {
  const rows = data
    .slice(0, 8)
    .map((d) => ({ ...d, label: titleCaseTag(d.misconception_tag) }))
  return (
    <ChartCard title="Most common misconceptions">
      {rows.length === 0 ? (
        <Empty />
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 40)}>
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32 }}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" tick={AXIS} allowDecimals={false} />
            <YAxis type="category" dataKey="label" width={150} tick={AXIS} />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              formatter={((v: number, _n: unknown, p: { payload: MisconceptionCount }) => [
                `${v} findings · ${p.payload.affected_students} students`,
                'Occurrences',
              ]) as never}
            />
            <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} barSize={20}>
              <LabelList dataKey="count" position="right" style={AXIS} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

export function PassRateChart({ data }: { data: AssignmentPassRate[] }) {
  const rows = data.map((d) => ({ ...d, pct: Math.round(d.pass_rate * 100) }))
  return (
    <ChartCard title="Pass rate by assignment">
      {rows.length === 0 ? (
        <Empty />
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 44)}>
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 40 }}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" domain={[0, 100]} tick={AXIS} unit="%" />
            <YAxis type="category" dataKey="title" width={150} tick={AXIS} />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              formatter={((v: number, _n: unknown, p: { payload: { submissions: number } }) => [
                `${v}% of ${p.payload.submissions} submissions`,
                'All tests passing',
              ]) as never}
            />
            <Bar dataKey="pct" radius={[0, 4, 4, 0]} barSize={22}>
              {rows.map((r, i) => (
                <Cell key={i} fill={r.pct >= 60 ? CHART_COLORS[2] : CHART_COLORS[1]} />
              ))}
              <LabelList
                dataKey="pct"
                position="right"
                formatter={((v: number) => `${v}%`) as never}
                style={AXIS}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

export function CategoryChart({ data }: { data: CategoryCount[] }) {
  const rows = data.map((d) => ({ ...d, label: CATEGORY_LABELS[d.category] }))
  return (
    <ChartCard title="Findings by category">
      {rows.length === 0 ? (
        <Empty />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={rows} margin={{ left: 8, right: 8, top: 16 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tick={AXIS} />
            <YAxis tick={AXIS} allowDecimals={false} />
            <Tooltip cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="count" fill={CHART_COLORS[4]} radius={[4, 4, 0, 0]} barSize={40}>
              <LabelList dataKey="count" position="top" style={AXIS} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

export function SubmissionsChart({ data }: { data: SubmissionsPerDay[] }) {
  return (
    <ChartCard title="Submissions over time">
      {data.length === 0 ? (
        <Empty />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
            <defs>
              <linearGradient id="subs" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS[0]} stopOpacity={0.35} />
                <stop offset="100%" stopColor={CHART_COLORS[0]} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="day" tick={AXIS} />
            <YAxis tick={AXIS} allowDecimals={false} />
            <Tooltip cursor={{ stroke: CHART_COLORS[0] }} />
            <Area
              type="monotone"
              dataKey="count"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              fill="url(#subs)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

function Empty() {
  return <p className="py-8 text-center text-sm text-slate-400">No data yet.</p>
}
