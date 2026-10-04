import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FindingCard } from './FindingCard'
import type { Finding } from '../api/types'

const finding: Finding = {
  id: 1,
  analyzer: 'bandit',
  rule_id: 'B608',
  severity: 'error',
  category: 'security',
  file: 'main.py',
  line_start: 12,
  line_end: 12,
  message: 'Possible SQL injection',
  snippet: "cur.execute(f\"...\")",
  misconception_tag: 'sql-injection',
}

describe('FindingCard', () => {
  it('shows severity, category and the humanised misconception tag', () => {
    render(<FindingCard finding={finding} />)
    expect(screen.getByText('Error')).toBeInTheDocument()
    expect(screen.getByText('Security')).toBeInTheDocument()
    expect(screen.getByText('Sql Injection')).toBeInTheDocument()
    expect(screen.getByText('Possible SQL injection')).toBeInTheDocument()
    expect(screen.getByText(/main\.py:12/)).toBeInTheDocument()
  })
})
