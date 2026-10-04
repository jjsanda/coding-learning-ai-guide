import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Home } from './pages/Home'
import { Join } from './pages/Join'
import { AssignmentList } from './pages/AssignmentList'
import { AssignmentDetail } from './pages/AssignmentDetail'
import { SubmissionView } from './pages/SubmissionView'
import { InstructorLogin } from './pages/InstructorLogin'
import { InstructorCourses } from './pages/InstructorCourses'
import { InstructorDashboard } from './pages/InstructorDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/join" element={<Join />} />
        <Route path="/assignments" element={<AssignmentList />} />
        <Route path="/assignments/:assignmentId" element={<AssignmentDetail />} />
        <Route path="/submissions/:submissionId" element={<SubmissionView />} />
        <Route path="/instructor" element={<InstructorLogin />} />
        <Route path="/instructor/courses" element={<InstructorCourses />} />
        <Route path="/instructor/courses/:courseId" element={<InstructorDashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
