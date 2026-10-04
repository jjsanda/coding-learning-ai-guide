import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { Layout } from '../components/Layout'
import { studentSession } from '../lib/session'

export function Join() {
  const navigate = useNavigate()
  const [joinCode, setJoinCode] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const resp = await api.join(joinCode.trim(), name.trim())
      studentSession.set({
        token: resp.student_token,
        studentId: resp.student_id,
        course: resp.course,
      })
      navigate('/assignments')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not join the course')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-md">
        <h1 className="text-2xl font-semibold">Join a course</h1>
        <p className="mt-1 text-sm text-slate-600">
          Enter the join code your instructor shared with the class.
        </p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Join code</span>
            <input
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder="ABCD1234"
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono uppercase tracking-widest focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Your name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ada Lovelace"
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </label>
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
            {busy ? 'Joining…' : 'Join course'}
          </button>
        </form>
      </div>
    </Layout>
  )
}
