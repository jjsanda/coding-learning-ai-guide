import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { instructorSession, studentSession, type StudentSession } from './session'

/** Returns the student session, redirecting to /join if absent. */
export function useStudentSession(): StudentSession | null {
  const navigate = useNavigate()
  const session = studentSession.get()
  useEffect(() => {
    if (!session) navigate('/join')
  }, [session, navigate])
  return session
}

/** Returns the instructor token, redirecting to /instructor if absent. */
export function useInstructorToken(): string | null {
  const navigate = useNavigate()
  const token = instructorSession.get()
  useEffect(() => {
    if (!token) navigate('/instructor')
  }, [token, navigate])
  return token
}
