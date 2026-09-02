import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Constraints from './pages/Constraints'
import Courses from './pages/Courses'
import Dashboard from './pages/Dashboard'
import Instructors from './pages/Instructors'
import Rooms from './pages/Rooms'
import Timetable from './pages/Timetable'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="timetable" element={<Timetable />} />
          <Route path="courses" element={<Courses />} />
          <Route path="instructors" element={<Instructors />} />
          <Route path="rooms" element={<Rooms />} />
          <Route path="constraints" element={<Constraints />} />
          <Route path="*" element={<div className="state">Page not found.</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
