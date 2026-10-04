import type { SubmissionStatus } from '../api/types'

const STEPS: { key: SubmissionStatus; label: string }[] = [
  { key: 'queued', label: 'Queued' },
  { key: 'running', label: 'Running in sandbox' },
  { key: 'analyzing', label: 'Analyzing' },
  { key: 'feedback', label: 'Writing feedback' },
  { key: 'completed', label: 'Done' },
]

const ORDER: SubmissionStatus[] = ['queued', 'running', 'analyzing', 'feedback', 'completed']

export function StatusStepper({ status }: { status: SubmissionStatus }) {
  if (status === 'failed') {
    return (
      <div className="rounded-lg bg-red-50 px-4 py-3 text-sm font-medium text-red-800 ring-1 ring-red-600/20">
        The sandbox run did not complete. See the error below.
      </div>
    )
  }
  const current = ORDER.indexOf(status)
  const complete = status === 'completed'
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm">
      {STEPS.map((step, i) => {
        const state = complete || i < current ? 'done' : i === current ? 'active' : 'todo'
        return (
          <li key={step.key} className="flex items-center gap-2">
            <span
              className={
                'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ' +
                (state === 'done'
                  ? 'bg-emerald-500 text-white'
                  : state === 'active'
                    ? 'bg-sky-500 text-white'
                    : 'bg-slate-200 text-slate-500')
              }
            >
              {state === 'done' ? '✓' : i + 1}
            </span>
            <span className={state === 'todo' ? 'text-slate-400' : 'font-medium'}>
              {step.label}
              {state === 'active' && <span className="ml-1 animate-pulse">…</span>}
            </span>
            {i < STEPS.length - 1 && <span className="text-slate-300">→</span>}
          </li>
        )
      })}
    </ol>
  )
}
