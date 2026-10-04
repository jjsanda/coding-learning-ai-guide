export type Language = 'python' | 'javascript'

export type SubmissionStatus =
  | 'queued'
  | 'running'
  | 'analyzing'
  | 'feedback'
  | 'completed'
  | 'failed'

export type Severity = 'info' | 'warning' | 'error' | 'critical'
export type Category = 'style' | 'complexity' | 'security' | 'bug_risk' | 'correctness'

export interface Meta {
  version: string
  execution_backend: string
  feedback_provider: string
}

export interface CoursePublic {
  id: string
  title: string
}

export interface JoinResponse {
  student_id: string
  student_token: string
  course: CoursePublic
}

export interface Course {
  id: string
  title: string
  join_code: string
  created_at: string
}

export interface TestCaseView {
  name: string
  stdin: string | null
  expected_stdout: string | null
  visible: boolean
}

export interface Assignment {
  id: string
  course_id: string
  title: string
  description_md: string
  language: Language
  entrypoint: string
  test_cases: TestCaseView[]
  created_at: string
}

export interface AssignmentSummary {
  id: string
  course_id: string
  title: string
  language: Language
  created_at: string
}

export interface SubmissionFile {
  path: string
  content: string
}

export interface TestResult {
  name: string
  passed: boolean
  expected: string | null
  actual: string | null
  duration_ms: number
  timed_out: boolean
}

export interface Finding {
  id: number
  analyzer: string
  rule_id: string
  severity: Severity
  category: Category
  file: string
  line_start: number
  line_end: number
  message: string
  snippet: string | null
  misconception_tag: string | null
}

export interface Submission {
  id: string
  assignment_id: string
  student_id: string
  status: SubmissionStatus
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  test_results: TestResult[]
  findings: Finding[]
}

export interface FeedbackItem {
  finding_ref: number | null
  explanation_md: string
  hint_md: string
  misconception_tag: string | null
}

export interface Feedback {
  submission_id: string
  provider: string
  model: string | null
  summary_md: string
  items: FeedbackItem[]
  next_steps: string[]
  cached: boolean
  created_at: string
}

export interface MisconceptionCount {
  misconception_tag: string
  count: number
  affected_students: number
}

export interface AssignmentPassRate {
  assignment_id: string
  title: string
  submissions: number
  pass_rate: number
}

export interface CategoryCount {
  category: Category
  count: number
}

export interface SubmissionsPerDay {
  day: string
  count: number
}

export interface CourseInsights {
  course_id: string
  total_submissions: number
  total_students: number
  misconceptions: MisconceptionCount[]
  pass_rates: AssignmentPassRate[]
  findings_by_category: CategoryCount[]
  submissions_per_day: SubmissionsPerDay[]
}
