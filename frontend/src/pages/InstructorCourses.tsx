import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Layout } from '../components/Layout'
import { instructorSession } from '../lib/session'
import { useInstructorToken } from '../lib/guards'

export function InstructorCourses() {
  const navigate = useNavigate()
  const token = useInstructorToken()

  const { data, isLoading } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(token!),
    enabled: !!token,
  })

  if (!token) return null

  return (
    <Layout
      right={
        <button
          onClick={() => {
            instructorSession.clear()
            navigate('/')
          }}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          Sign out
        </button>
      }
    >
      <h1 className="text-2xl font-semibold">Your courses</h1>
      {isLoading && <p className="mt-6 text-slate-500">Loading…</p>}
      {data && data.length === 0 && (
        <p className="mt-6 text-slate-500">You haven't created any courses yet.</p>
      )}
      <ul className="mt-6 space-y-3">
        {data?.map((c) => (
          <li key={c.id}>
            <Link
              to={`/instructor/courses/${c.id}`}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 hover:border-sky-300 hover:shadow-sm"
            >
              <span className="font-medium">{c.title}</span>
              <span className="font-mono text-xs text-slate-500">join: {c.join_code}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Layout>
  )
}
