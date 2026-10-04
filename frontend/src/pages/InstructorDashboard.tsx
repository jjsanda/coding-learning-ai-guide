import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  CategoryChart,
  MisconceptionChart,
  PassRateChart,
  SubmissionsChart,
} from '../components/charts'
import { Layout } from '../components/Layout'
import { useInstructorToken } from '../lib/guards'
import { titleCaseTag } from '../lib/ui'

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  )
}

export function InstructorDashboard() {
  const { courseId } = useParams()
  const navigate = useNavigate()
  const token = useInstructorToken()

  const { data, isLoading } = useQuery({
    queryKey: ['insights', courseId],
    queryFn: () => api.getInsights(courseId!, token!),
    enabled: !!token,
    refetchInterval: 10000,
  })

  if (!token) return null

  return (
    <Layout
      right={
        <button
          onClick={() => navigate('/instructor/courses')}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          All courses
        </button>
      }
    >
      <h1 className="text-2xl font-semibold">Class insights</h1>
      <p className="mt-1 text-sm text-slate-500">
        Aggregated from deterministic analyzer findings — reproducible, not model-generated.
      </p>

      {isLoading && <p className="mt-6 text-slate-500">Loading…</p>}
      {data && (
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Students" value={data.total_students} />
            <Stat label="Submissions" value={data.total_submissions} />
            <Stat label="Assignments" value={data.pass_rates.length} />
            <Stat
              label="Distinct misconceptions"
              value={data.misconceptions.length}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <MisconceptionChart data={data.misconceptions} />
            <PassRateChart data={data.pass_rates} />
            <CategoryChart data={data.findings_by_category} />
            <SubmissionsChart data={data.submissions_per_day} />
          </div>

          {data.misconceptions.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-4 py-2 font-medium">Misconception</th>
                    <th className="px-4 py-2 font-medium">Occurrences</th>
                    <th className="px-4 py-2 font-medium">Students affected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.misconceptions.map((m) => (
                    <tr key={m.misconception_tag}>
                      <td className="px-4 py-2 font-medium">
                        {titleCaseTag(m.misconception_tag)}
                      </td>
                      <td className="px-4 py-2 tabular-nums">{m.count}</td>
                      <td className="px-4 py-2 tabular-nums">{m.affected_students}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}
