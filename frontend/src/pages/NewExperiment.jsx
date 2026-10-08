import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../app-context'
import { Alert, Icon, Spinner } from '../components/bits'
import AlgorithmStep from './wizard/AlgorithmStep'
import DatasetStep from './wizard/DatasetStep'
import FeaturesStep from './wizard/FeaturesStep'
import PreprocessStep from './wizard/PreprocessStep'
import ReviewStep from './wizard/ReviewStep'
import TargetStep from './wizard/TargetStep'
import { defaultParams, guessProblem } from './wizard/helpers'

const STEPS = ['Dataset', 'Target', 'Features', 'Preprocessing', 'Algorithm', 'Review']

const DEFAULT_PREP = { missing: 'median', encoding: 'onehot', scaling: 'standard', test_size: 0.2, random_state: 42 }

export default function NewExperiment() {
  const { config } = useApp()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [reached, setReached] = useState(0)
  const [dataset, setDataset] = useState(null)
  const [target, setTarget] = useState(null)
  const [problem, setProblem] = useState('classification')
  const [features, setFeatures] = useState([])
  const [prep, setPrep] = useState(DEFAULT_PREP)
  const [algo, setAlgo] = useState(null)
  const [params, setParams] = useState({})
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const profile = dataset?.profile
  const cols = useMemo(() => Object.fromEntries((profile?.columns ?? []).map((c) => [c.name, c])), [profile])

  function chooseAlgorithm(problemType, key) {
    const spec = config.algorithms[problemType].find((a) => a.key === key)
    setAlgo(key)
    setParams(defaultParams(spec))
  }

  function onDataset(ds) {
    const p = ds.profile
    setDataset(ds)
    pickTarget(ds, p.suggested_target)
    setPrep(DEFAULT_PREP)
    setError('')
  }

  function pickTarget(ds, name) {
    const col = ds.profile.columns.find((c) => c.name === name)
    const known = ds.profile.target_candidates.find((t) => t.name === name)
    const pt = known?.problem_type ?? guessProblem(col)
    setTarget(name)
    setProblem(pt)
    setFeatures(ds.profile.columns.filter((c) => !c.exclude_default && c.name !== name).map((c) => c.name))
    chooseAlgorithm(pt, pt === 'classification' ? 'random_forest' : 'random_forest_regressor')
  }

  function changeProblem(pt) {
    setProblem(pt)
    chooseAlgorithm(pt, pt === 'classification' ? 'random_forest' : 'random_forest_regressor')
  }

  const go = (n) => { setStep(n); setReached((r) => Math.max(r, n)); setError('') }

  const canContinue = [
    !!dataset,
    !!target && (problem === 'classification' || ['integer', 'float'].includes(cols[target]?.kind)),
    features.length > 0,
    true,
    !!algo,
    true,
  ][step]

  async function run() {
    setRunning(true)
    setError('')
    try {
      const { id } = await api.createExperiment({
        dataset_id: dataset.id, target, problem_type: problem, features, algorithm: algo, params, preprocessing: prep,
      })
      navigate(`/experiments/${id}`)
    } catch (err) {
      setError(err.message)
      setRunning(false)
    }
  }

  const shared = { profile, cols, target, problem, features, prep, algo, params }

  return (
    <div className="page wide">
      <header className="page-head">
        <div>
          <h1>New experiment</h1>
          <p className="lede">Six short steps from a table of data to a measured model.</p>
        </div>
      </header>

      <div className="wizard">
        <ol className="rail" aria-label="Steps">
          {STEPS.map((name, i) => (
            <li key={name} className={`${i === step ? 'current' : ''} ${i < step || (i <= reached && i !== step) ? 'seen' : ''}`}>
              <button disabled={i > reached || (i > 0 && !dataset)} onClick={() => go(i)} aria-current={i === step ? 'step' : undefined}>
                <span className="rail-num">{i < step ? Icon.check : i + 1}</span>
                <span>{name}</span>
              </button>
            </li>
          ))}
        </ol>

        <section className="wizard-panel" aria-live="polite">
          {step === 0 && <DatasetStep dataset={dataset} onDataset={onDataset} onClear={() => { setDataset(null); setReached(0) }} />}
          {step === 1 && <TargetStep {...shared} onTarget={(n) => pickTarget(dataset, n)} onProblem={changeProblem} />}
          {step === 2 && <FeaturesStep {...shared} onChange={setFeatures} />}
          {step === 3 && <PreprocessStep prep={prep} onChange={setPrep} />}
          {step === 4 && <AlgorithmStep problem={problem} algo={algo} params={params} onAlgo={(k) => chooseAlgorithm(problem, k)} onParams={setParams} />}
          {step === 5 && <ReviewStep {...shared} dataset={dataset} />}

          <Alert>{error}</Alert>

          <footer className="wizard-nav">
            <button className="btn" onClick={() => go(step - 1)} disabled={step === 0 || running}>Back</button>
            {step < STEPS.length - 1 ? (
              <button className="btn btn-primary" onClick={() => go(step + 1)} disabled={!canContinue}>
                Continue to {STEPS[step + 1].toLowerCase()}
              </button>
            ) : (
              <button className="btn btn-primary btn-lg" onClick={run} disabled={running}>
                {running ? <><Spinner /> Sending to EC2</> : 'Run experiment'}
              </button>
            )}
          </footer>
        </section>
      </div>
    </div>
  )
}
