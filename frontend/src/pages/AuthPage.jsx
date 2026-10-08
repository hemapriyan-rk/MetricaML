import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../app-context'
import { Alert, Brand, Spinner } from '../components/bits'
import Ruler from '../components/Ruler'

export default function AuthPage({ mode }) {
  const register = mode === 'register'
  const { refresh } = useApp()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (register) await api.register(form.name, form.email, form.password)
      else await api.login(form.email, form.password)
      await refresh()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <section className="auth-hero" aria-label="About MetricaML">
        <Brand light />
        <div className="auth-pitch">
          <h1>Measure every model you train.</h1>
          <p>
            Upload a table, choose what to predict and how, and MetricaML trains it on an AWS EC2
            server, then shows how well it did and gives you the model to keep.
          </p>
        </div>
        <figure className="auth-ruler">
          <figcaption>Accuracy on held-out rows, from an example run</figcaption>
          <div className="auth-reading">94.2%</div>
          <Ruler value={0.942} baseline={0.61} size="lg" baselineLabel="Always guessing the most common class" tone="light" />
          <p className="auth-note">The open mark shows what guessing the most common answer would have scored.</p>
        </figure>
      </section>

      <section className="auth-form-wrap">
        <form className="auth-form" onSubmit={submit} noValidate>
          <h2>{register ? 'Create your account' : 'Sign in'}</h2>
          <p className="muted">{register ? 'Your experiments and files stay private to your account.' : 'Welcome back. Pick up where you left off.'}</p>

          {register && (
            <label className="field">
              <span>Name</span>
              <input value={form.name} onChange={set('name')} autoComplete="name" required maxLength={60} />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input type="email" value={form.email} onChange={set('email')} autoComplete="email" required />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={form.password} onChange={set('password')} required minLength={8}
                   autoComplete={register ? 'new-password' : 'current-password'} />
            {register && <small>At least 8 characters.</small>}
          </label>

          <Alert>{error}</Alert>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? <Spinner /> : null}{register ? 'Create account' : 'Sign in'}
          </button>
          <p className="switch">
            {register ? <>Already have an account? <Link to="/login">Sign in</Link></> : <>New to MetricaML? <Link to="/register">Create an account</Link></>}
          </p>
        </form>
      </section>
    </div>
  )
}
