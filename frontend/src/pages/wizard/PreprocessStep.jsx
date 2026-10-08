export default function PreprocessStep({ prep, onChange }) {
  const set = (k, v) => onChange({ ...prep, [k]: v })
  return (
    <div>
      <h2>Prepare the data</h2>
      <p className="muted">These steps run automatically before training, fitted on the training rows only so the test rows stay unseen.</p>

      <div className="form-grid">
        <label className="field">
          <span>Missing numbers</span>
          <select value={prep.missing} onChange={(e) => set('missing', e.target.value)}>
            <option value="median">Fill with the median</option>
            <option value="mean">Fill with the mean</option>
            <option value="most_frequent">Fill with the most frequent value</option>
          </select>
          <small>Missing categories are always filled with the most frequent one.</small>
        </label>

        <label className="field">
          <span>Categorical columns</span>
          <select value={prep.encoding} onChange={(e) => set('encoding', e.target.value)}>
            <option value="onehot">One-hot encoding</option>
            <option value="ordinal">Ordinal encoding</option>
          </select>
          <small>One-hot gives each category its own column. Ordinal uses one column of numbers.</small>
        </label>

        <label className="field">
          <span>Scaling of numeric columns</span>
          <select value={prep.scaling} onChange={(e) => set('scaling', e.target.value)}>
            <option value="standard">Standard scaling</option>
            <option value="minmax">Min–max scaling</option>
            <option value="none">No scaling</option>
          </select>
          <small>Helps distance-based and linear models. Trees don’t need it.</small>
        </label>

        <label className="field">
          <span>Train / test split</span>
          <select value={prep.test_size} onChange={(e) => set('test_size', Number(e.target.value))}>
            {[0.1, 0.2, 0.3, 0.4, 0.5].map((t) => <option key={t} value={t}>{Math.round((1 - t) * 100)} / {Math.round(t * 100)}</option>)}
          </select>
          <small>The test share is held back to measure the model.</small>
        </label>

        <label className="field">
          <span>Random state</span>
          <input type="number" min="0" max="2147483647" value={prep.random_state}
                 onChange={(e) => set('random_state', Math.max(0, Math.floor(Number(e.target.value) || 0)))} />
          <small>Keep it the same to reproduce a run exactly.</small>
        </label>
      </div>
    </div>
  )
}
