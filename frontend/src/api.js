async function request(path, { method = 'GET', body } = {}) {
  const opts = { method, credentials: 'same-origin', headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch('/api' + path, opts)
  } catch {
    throw new Error('Could not reach the MetricaML server. Check your connection and try again.')
  }
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const err = new Error(data?.detail || `Something went wrong (error ${res.status}).`)
    err.status = res.status
    throw err
  }
  return data
}

// Upload with progress, which fetch can't report.
function upload(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/datasets')
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onerror = () => reject(new Error('The upload was interrupted. Check your connection and try again.'))
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else {
        const err = new Error(data?.detail || (xhr.status === 413 ? 'That file is too large.' : `Upload failed (error ${xhr.status}).`))
        err.status = xhr.status
        reject(err)
      }
    }
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}

export const api = {
  me: () => request('/auth/me'),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  register: (name, email, password) => request('/auth/register', { method: 'POST', body: { name, email, password } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  config: () => request('/config'),
  upload,
  useSample: (name) => request(`/datasets/sample/${encodeURIComponent(name)}`, { method: 'POST' }),
  createExperiment: (body) => request('/experiments', { method: 'POST', body }),
  experiments: () => request('/experiments'),
  experiment: (id) => request(`/experiments/${id}`),
  deleteExperiment: (id) => request(`/experiments/${id}`, { method: 'DELETE' }),
}
