import type { Finding } from '../api/types'
import { CATEGORY_LABELS, SEVERITY_STYLES, titleCaseTag } from '../lib/ui'

export function FindingCard({ finding }: { finding: Finding }) {
  const sev = SEVERITY_STYLES[finding.severity]
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${sev.className}`}
        >
          {sev.label}
        </span>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {CATEGORY_LABELS[finding.category]}
        </span>
        {finding.misconception_tag && (
          <span className="rounded-md bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
            {titleCaseTag(finding.misconception_tag)}
          </span>
        )}
        <span className="ml-auto font-mono text-xs text-slate-400">
          {finding.file}
          {finding.line_start > 0 && `:${finding.line_start}`} · {finding.analyzer}/{finding.rule_id}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-700">{finding.message}</p>
      {finding.snippet && (
        <pre className="mt-2 overflow-x-auto rounded-md bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
          <code>{finding.snippet}</code>
        </pre>
      )}
    </div>
  )
}
