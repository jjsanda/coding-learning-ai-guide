import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { Layout } from '../components/Layout'
import { instructorSession } from '../lib/session'

export function InstructorLogin() {
  const navigate = useNavigate()
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.listCourses(token.trim()) // validates the token
      instructorSession.set(token.trim())
      navigate('/instructor/courses')
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'That token was not recognised.'
          : 'Could not sign in.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-md">
        <h1 className="text-2xl font-semibold">Instructor sign-in</h1>
        <p className="mt-1 text-sm text-slate-600">
          Paste the API token printed by{' '}
          <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">
            codeguide create-instructor
          </code>
          .
        </p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="cgi_…"
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-600/20">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-sky-600 px-4 py-2.5 font-medium text-white hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </Layout>
  )
}
