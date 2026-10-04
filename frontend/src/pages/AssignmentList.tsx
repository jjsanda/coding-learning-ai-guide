import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Layout } from '../components/Layout'
import { studentSession } from '../lib/session'
import { useStudentSession } from '../lib/guards'

export function AssignmentList() {
  const navigate = useNavigate()
  const session = useStudentSession()

  const { data, isLoading } = useQuery({
    queryKey: ['assignments', session?.course.id],
    queryFn: () => api.listAssignments(session!.course.id, session!.token),
    enabled: !!session,
  })

  if (!session) return null

  return (
    <Layout
      right={
        <button
          onClick={() => {
            studentSession.clear()
            navigate('/')
          }}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          Leave course
        </button>
      }
    >
      <p className="text-sm text-slate-500">{session.course.title}</p>
      <h1 className="mt-1 text-2xl font-semibold">Assignments</h1>

      {isLoading && <p className="mt-6 text-slate-500">Loading…</p>}
      {data && data.length === 0 && (
        <p className="mt-6 text-slate-500">No assignments have been posted yet.</p>
      )}
      <ul className="mt-6 space-y-3">
        {data?.map((a) => (
          <li key={a.id}>
            <Link
              to={`/assignments/${a.id}`}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 hover:border-sky-300 hover:shadow-sm"
            >
              <span className="font-medium">{a.title}</span>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
                {a.language}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Layout>
  )
}
