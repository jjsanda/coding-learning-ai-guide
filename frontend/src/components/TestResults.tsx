import type { TestResult } from '../api/types'

export function TestResults({ results }: { results: TestResult[] }) {
  if (results.length === 0) {
    return <p className="text-sm text-slate-500">This assignment has no automated tests.</p>
  }
  const passed = results.filter((r) => r.passed).length
  return (
    <div>
      <p className="mb-3 text-sm font-medium text-slate-700">
        {passed} of {results.length} tests passing
      </p>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {results.map((r) => (
          <li key={r.name} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span
              className={
                'flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold text-white ' +
                (r.passed ? 'bg-emerald-500' : 'bg-red-500')
              }
              aria-label={r.passed ? 'passed' : 'failed'}
            >
              {r.passed ? '✓' : '✕'}
            </span>
            <span className="font-mono">{r.name}</span>
            {r.timed_out && (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
                timed out
              </span>
            )}
            <span className="ml-auto text-xs text-slate-400">{r.duration_ms} ms</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
