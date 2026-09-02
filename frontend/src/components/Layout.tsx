import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/timetable', label: 'Timetable' },
  { to: '/courses', label: 'Courses' },
  { to: '/instructors', label: 'Instructors' },
  { to: '/rooms', label: 'Rooms' },
  { to: '/constraints', label: 'Constraints' },
]

export default function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">◷</span>
          <div>
            <strong>Chronos</strong>
            <small>Automated Timetabling</small>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <footer className="sidebar-foot">
          <small>KMUTT SIT · Capstone</small>
        </footer>
      </aside>
      <main className="content"><Outlet /></main>
    </div>
  )
}
