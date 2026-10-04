import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { FeedbackPanel } from '../components/FeedbackPanel'
import { FindingCard } from '../components/FindingCard'
import { Layout } from '../components/Layout'
import { StatusStepper } from '../components/StatusStepper'
import { TestResults } from '../components/TestResults'
import { CATEGORY_LABELS, CATEGORY_ORDER } from '../lib/ui'
import { useStudentSession } from '../lib/guards'
import type { Finding } from '../api/types'

const TERMINAL = new Set(['completed', 'failed'])

export function SubmissionView() {
  const { submissionId } = useParams()
  const navigate = useNavigate()
  const session = useStudentSession()

  const { data: submission } = useQuery({
    queryKey: ['submission', submissionId],
    queryFn: () => api.getSubmission(submissionId!, session!.token),
    enabled: !!session,
    refetchInterval: (query) =>
      query.state.data && TERMINAL.has(query.state.data.status) ? false : 1500,
  })

  const done = submission && submission.status === 'completed'
  const { data: feedback } = useQuery({
    queryKey: ['feedback', submissionId],
    queryFn: () => api.getFeedback(submissionId!, session!.token),
    enabled: !!done && !!session,
  })

  if (!session) return null
  if (!submission) {
    return (
      <Layout>
        <p className="text-slate-500">Loading…</p>
      </Layout>
    )
  }

  const byCategory = new Map<string, Finding[]>()
  for (const f of submission.findings) {
    if (!byCategory.has(f.category)) byCategory.set(f.category, [])
    byCategory.get(f.category)!.push(f)
  }

  return (
    <Layout>
      <button
        onClick={() => navigate('/assignments')}
        className="text-sm text-slate-500 hover:text-slate-700"
      >
        ← Back to assignments
      </button>
      <h1 className="mt-2 text-2xl font-semibold">Submission feedback</h1>

      <div className="mt-4">
        <StatusStepper status={submission.status} />
      </div>
      {submission.error && (
        <pre className="mt-3 overflow-x-auto rounded-lg bg-red-50 p-3 text-sm text-red-800">
          {submission.error}
        </pre>
      )}

      {done && (
        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <div className="space-y-6">
            <section>
              <h2 className="mb-3 text-lg font-semibold">Tests</h2>
              <TestResults results={submission.test_results} />
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">
                Analysis ({submission.findings.length} findings)
              </h2>
              <div className="space-y-4">
                {CATEGORY_ORDER.filter((c) => byCategory.has(c)).map((c) => (
                  <div key={c}>
                    <h3 className="mb-2 text-sm font-medium text-slate-500">
                      {CATEGORY_LABELS[c]}
                    </h3>
                    <div className="space-y-3">
                      {byCategory.get(c)!.map((f) => (
                        <FindingCard key={f.id} finding={f} />
                      ))}
                    </div>
                  </div>
                ))}
                {submission.findings.length === 0 && (
                  <p className="text-sm text-slate-500">
                    No issues flagged — the analyzers were happy.
                  </p>
                )}
              </div>
            </section>
          </div>
          <div>
            <h2 className="mb-3 text-lg font-semibold">Feedback</h2>
            {feedback ? (
              <FeedbackPanel feedback={feedback} />
            ) : (
              <p className="text-sm text-slate-500">Preparing feedback…</p>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
