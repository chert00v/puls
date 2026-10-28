import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home.jsx'
import TeacherDashboard from './pages/TeacherDashboard.jsx'
import TeacherReview from './pages/TeacherReview.jsx'
import TeacherResults from './pages/TeacherResults.jsx'
import StudentQuiz from './pages/StudentQuiz.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/teacher/:id" element={<TeacherDashboard />} />
      <Route path="/teacher/:id/review" element={<TeacherReview />} />
      <Route path="/teacher/:id/results" element={<TeacherResults />} />
      <Route path="/join/:code" element={<StudentQuiz />} />
      <Route path="*" element={<p className="p-6">Страница не найдена</p>} />
    </Routes>
  )
}
