import type {
  Assignment,
  AssignmentSummary,
  Course,
  CourseInsights,
  Feedback,
  JoinResponse,
  Meta,
  Submission,
  SubmissionFile,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const resp = await fetch(`/api/v1${path}`, { ...init, headers: { ...headers, ...init?.headers } })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail ?? detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(resp.status, typeof detail === 'string' ? detail : 'Request failed')
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  meta: () => request<Meta>('/meta', null),

  join: (joinCode: string, displayName: string) =>
    request<JoinResponse>('/auth/join', null, {
      method: 'POST',
      body: JSON.stringify({ join_code: joinCode, display_name: displayName }),
    }),

  listAssignments: (courseId: string, token: string) =>
    request<AssignmentSummary[]>(`/courses/${courseId}/assignments`, token),

  getAssignment: (assignmentId: string, token: string) =>
    request<Assignment>(`/assignments/${assignmentId}`, token),

  submit: (assignmentId: string, files: SubmissionFile[], token: string) =>
    request<{ submission_id: string; status: string }>(
      `/assignments/${assignmentId}/submissions`,
      token,
      { method: 'POST', body: JSON.stringify({ files }) },
    ),

  getSubmission: (submissionId: string, token: string) =>
    request<Submission>(`/submissions/${submissionId}`, token),

  getFeedback: (submissionId: string, token: string) =>
    request<Feedback>(`/submissions/${submissionId}/feedback`, token),

  // instructor
  listCourses: (token: string) => request<Course[]>('/courses', token),
  getInsights: (courseId: string, token: string) =>
    request<CourseInsights>(`/courses/${courseId}/insights`, token),
}
