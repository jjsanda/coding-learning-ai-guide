import type { Category, Severity } from '../api/types'

// Validated categorical palette (see dataviz validator: all CVD/normal-vision
// checks pass; contrast WARN is covered by direct labels + legends).
export const CHART_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#14b8a6']

export const SEVERITY_STYLES: Record<Severity, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-100 text-red-800 ring-red-600/20' },
  error: { label: 'Error', className: 'bg-orange-100 text-orange-800 ring-orange-600/20' },
  warning: { label: 'Warning', className: 'bg-amber-100 text-amber-800 ring-amber-600/20' },
  info: { label: 'Info', className: 'bg-slate-100 text-slate-700 ring-slate-500/20' },
}

export const CATEGORY_LABELS: Record<Category, string> = {
  security: 'Security',
  correctness: 'Correctness',
  bug_risk: 'Bug risk',
  complexity: 'Complexity',
  style: 'Style',
}

export const CATEGORY_ORDER: Category[] = [
  'security',
  'correctness',
  'bug_risk',
  'complexity',
  'style',
]

export function titleCaseTag(tag: string): string {
  return tag
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}
