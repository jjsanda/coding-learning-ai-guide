import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function Layout({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-sky-500">{'{ }'}</span>
            <span className="text-lg font-semibold tracking-tight">coding-learning-ai-guide</span>
          </Link>
          <div>{right}</div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
