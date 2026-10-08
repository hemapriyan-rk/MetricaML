import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from './api'
import { AppContext, useApp } from './app-context'
import { Brand, Icon, Spinner } from './components/bits'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import Experiments from './pages/Experiments'
import ExperimentPage from './pages/ExperimentPage'
import NewExperiment from './pages/NewExperiment'
import Profile from './pages/Profile'

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = still checking the session
  const [config, setConfig] = useState(null)

  const loadSession = useCallback(async () => {
    try {
      const [me, cfg] = await Promise.all([api.me(), api.config()])
      setConfig(cfg) // set together: a user without config would bounce a refreshed page to the dashboard
      setUser(me)
    } catch {
      setUser(null)
      setConfig(null)
    }
  }, [])

  useEffect(() => { loadSession() }, [loadSession])

  const value = useMemo(() => ({
    user, config, refresh: loadSession,
    signOut: async () => { await api.logout().catch(() => {}); setUser(null); setConfig(null) },
  }), [user, config, loadSession])

  if (user === undefined) return <div className="boot"><Spinner label="Loading MetricaML" /></div>

  return (
    <AppContext.Provider value={value}>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <AuthPage mode="login" />} />
        <Route path="/register" element={user ? <Navigate to="/" replace /> : <AuthPage mode="register" />} />
        <Route element={user && config ? <Shell /> : <Navigate to="/login" replace />}>
          <Route index element={<Dashboard />} />
          <Route path="new" element={<NewExperiment />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="experiments/:id" element={<ExperimentPage />} />
          <Route path="profile" element={<Profile />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppContext.Provider>
  )
}

function Shell() {
  const { user, signOut } = useApp()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <aside className="sidebar">
        <NavLink to="/" className="brand-link" aria-label="MetricaML home"><Brand /></NavLink>
        <nav aria-label="Main">
          <NavLink to="/" end>{Icon.grid}<span>Dashboard</span></NavLink>
          <NavLink to="/new">{Icon.plus}<span>New experiment</span></NavLink>
          <NavLink to="/experiments">{Icon.list}<span>My experiments</span></NavLink>
          <NavLink to="/profile">{Icon.user}<span>Profile</span></NavLink>
        </nav>
        <div className="sidebar-user">
          <div className="who">
            <strong>{user.name}</strong>
            <span>{user.email}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={async () => { await signOut(); navigate('/login') }}>
            {Icon.out} Sign out
          </button>
        </div>
      </aside>
      <main id="main" className="main"><Outlet /></main>
    </div>
  )
}
