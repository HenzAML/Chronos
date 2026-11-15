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
          <img src="/chronos-wordmark.svg" alt="Chronos" />
          <small>An Automated Timetabling Solution</small>
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
          <img src="/chronos-mascot.svg" alt="" />
          <em>Better Schedules for Brighter Futures</em>
          <small>KMUTT • SIT Capstone Project 2026</small>
        </footer>
      </aside>
      <main className="content"><Outlet /></main>
    </div>
  )
}
