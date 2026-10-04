import ReactMarkdown from 'react-markdown'
import type { Feedback } from '../api/types'
import { titleCaseTag } from '../lib/ui'

function providerLabel(feedback: Feedback): string {
  if (feedback.provider === 'template') return 'Built-in explanations (no LLM configured)'
  if (feedback.provider === 'template(fallback)')
    return 'Built-in explanations (LLM provider was unavailable)'
  const model = feedback.model ? ` · ${feedback.model}` : ''
  return `Generated with ${feedback.provider}${model}`
}

export function FeedbackPanel({ feedback }: { feedback: Feedback }) {
  return (
    <div className="space-y-4">
      <div className="prose prose-sm prose-slate max-w-none rounded-lg border border-slate-200 bg-white p-4">
        <ReactMarkdown>{feedback.summary_md}</ReactMarkdown>
      </div>

      {feedback.items.map((item, i) => (
        <div key={i} className="rounded-lg border border-slate-200 bg-white p-4">
          {item.misconception_tag && (
            <span className="mb-2 inline-block rounded-md bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
              {titleCaseTag(item.misconception_tag)}
            </span>
          )}
          <div className="prose prose-sm prose-slate max-w-none">
            <ReactMarkdown>{item.explanation_md}</ReactMarkdown>
          </div>
          {item.hint_md && (
            <p className="mt-2 border-l-2 border-sky-300 pl-3 text-sm italic text-slate-600">
              {item.hint_md}
            </p>
          )}
        </div>
      ))}

      {feedback.next_steps.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Next steps</h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {feedback.next_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-slate-400">
        {providerLabel(feedback)}
        {feedback.cached && ' · served from cache'}. Feedback is formative — it explains the
        analysis; the fixes are yours to make.
      </p>
    </div>
  )
}
