import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { CodeEditor } from '../components/CodeEditor'
import { Layout } from '../components/Layout'
import { useStudentSession } from '../lib/guards'

const STARTERS: Record<string, string> = {
  python: '# Read input and print your answer.\n',
  javascript: "// Read input from process.stdin and console.log your answer.\n",
}

export function AssignmentDetail() {
  const { assignmentId } = useParams()
  const navigate = useNavigate()
  const session = useStudentSession()

  const { data: assignment, isLoading } = useQuery({
    queryKey: ['assignment', assignmentId],
    queryFn: () => api.getAssignment(assignmentId!, session!.token),
    enabled: !!session,
  })

  const [code, setCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const editorValue = useMemo(() => {
    if (code !== null) return code
    return assignment ? (STARTERS[assignment.language] ?? '') : ''
  }, [code, assignment])

  if (!session) return null
  if (isLoading || !assignment) {
    return (
      <Layout>
        <p className="text-slate-500">Loading…</p>
      </Layout>
    )
  }

  const current = assignment
  const token = session.token

  async function submit() {
    setError(null)
    setBusy(true)
    try {
      const resp = await api.submit(
        current.id,
        [{ path: current.entrypoint, content: editorValue }],
        token,
      )
      navigate(`/submissions/${resp.submission_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Submission failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout>
      <button
        onClick={() => navigate('/assignments')}
        className="text-sm text-slate-500 hover:text-slate-700"
      >
        ← Back to assignments
      </button>
      <h1 className="mt-2 text-2xl font-semibold">{assignment.title}</h1>

      <div className="mt-6 grid gap-8 lg:grid-cols-2">
        <div>
          <div className="prose prose-sm prose-slate max-w-none rounded-lg border border-slate-200 bg-white p-4">
            <ReactMarkdown>{assignment.description_md}</ReactMarkdown>
          </div>
          {assignment.test_cases.length > 0 && (
            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-800">Example tests</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {assignment.test_cases.map((t) => (
                  <li key={t.name} className="font-mono text-xs">
                    {t.name}
                    {t.visible && t.expected_stdout != null ? (
                      <span className="text-slate-400">
                        {' '}
                        · in {JSON.stringify(t.stdin)} → out {JSON.stringify(t.expected_stdout)}
                      </span>
                    ) : (
                      <span className="text-slate-400"> · hidden</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">
            Your solution — <span className="font-mono">{assignment.entrypoint}</span>
          </p>
          <CodeEditor value={editorValue} onChange={setCode} language={assignment.language} />
          {error && (
            <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-600/20">
              {error}
            </p>
          )}
          <button
            onClick={submit}
            disabled={busy}
            className="mt-3 w-full rounded-lg bg-sky-600 px-4 py-2.5 font-medium text-white hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? 'Submitting…' : 'Submit for feedback'}
          </button>
        </div>
      </div>
    </Layout>
  )
}
