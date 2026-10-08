import { useNavigate } from 'react-router-dom'
import { useApp } from '../app-context'

export default function Profile() {
  const { user, signOut } = useApp()
  const navigate = useNavigate()
  return (
    <div className="page narrow">
      <header className="page-head">
        <div><h1>Profile</h1><p className="lede">Your account on this MetricaML server.</p></div>
      </header>
      <dl className="facts facts-wide">
        <div><dt>Name</dt><dd>{user.name}</dd></div>
        <div><dt>Email</dt><dd>{user.email}</dd></div>
        <div><dt>Member since</dt><dd>{new Date(user.created_at).toLocaleDateString('en', { dateStyle: 'long' })}</dd></div>
        <div><dt>Experiments</dt><dd>{user.experiments} run, {user.completed} completed</dd></div>
        <div><dt>Datasets uploaded</dt><dd>{user.datasets}</dd></div>
      </dl>
      <button className="btn" onClick={async () => { await signOut(); navigate('/login') }}>Sign out</button>
    </div>
  )
}
