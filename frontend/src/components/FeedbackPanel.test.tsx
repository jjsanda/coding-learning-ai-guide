import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FeedbackPanel } from './FeedbackPanel'
import type { Feedback } from '../api/types'

function make(overrides: Partial<Feedback> = {}): Feedback {
  return {
    submission_id: 's1',
    provider: 'template',
    model: null,
    summary_md: 'You passed **2 of 3** tests.',
    items: [
      {
        finding_ref: 1,
        explanation_md: 'This is an SQL injection risk.',
        hint_md: 'What could a user type here?',
        misconception_tag: 'sql-injection',
      },
    ],
    next_steps: ['Fix the query'],
    cached: false,
    created_at: '2026-07-16T00:00:00Z',
    ...overrides,
  }
}

describe('FeedbackPanel', () => {
  it('renders the summary, items, hint and next steps', () => {
    render(<FeedbackPanel feedback={make()} />)
    expect(screen.getByText(/passed/)).toBeInTheDocument()
    expect(screen.getByText('This is an SQL injection risk.')).toBeInTheDocument()
    expect(screen.getByText('What could a user type here?')).toBeInTheDocument()
    expect(screen.getByText('Fix the query')).toBeInTheDocument()
  })

  it('is honest about the built-in (no-LLM) attribution', () => {
    render(<FeedbackPanel feedback={make({ provider: 'template' })} />)
    expect(screen.getByText(/Built-in explanations/)).toBeInTheDocument()
  })

  it('flags a degraded fallback', () => {
    render(<FeedbackPanel feedback={make({ provider: 'template(fallback)' })} />)
    expect(screen.getByText(/LLM provider was unavailable/)).toBeInTheDocument()
  })
})
