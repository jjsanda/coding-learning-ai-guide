import type { CoursePublic } from '../api/types'

const STUDENT_KEY = 'clag.student'
const INSTRUCTOR_KEY = 'clag.instructor'

export interface StudentSession {
  token: string
  studentId: string
  course: CoursePublic
}

export const studentSession = {
  get(): StudentSession | null {
    const raw = localStorage.getItem(STUDENT_KEY)
    return raw ? (JSON.parse(raw) as StudentSession) : null
  },
  set(session: StudentSession) {
    localStorage.setItem(STUDENT_KEY, JSON.stringify(session))
  },
  clear() {
    localStorage.removeItem(STUDENT_KEY)
  },
}

export const instructorSession = {
  get(): string | null {
    return localStorage.getItem(INSTRUCTOR_KEY)
  },
  set(token: string) {
    localStorage.setItem(INSTRUCTOR_KEY, token)
  },
  clear() {
    localStorage.removeItem(INSTRUCTOR_KEY)
  },
}
