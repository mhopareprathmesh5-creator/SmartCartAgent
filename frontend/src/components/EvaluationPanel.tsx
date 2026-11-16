import { CheckCircle2, FlaskConical, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Evaluation } from '../api'
import { api, rupees } from '../api'

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      <div className="a-sub">{note}</div>
    </div>
  )
}

/** Milestone 7: the latest run of scripts/07_evaluate.py (read from docs/evaluation/results.json). */
export function EvaluationPanel() {
  const [ev, setEv] = useState<Evaluation | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    api.admin.evaluation().then(setEv).catch(() => setMissing(true))
  }, [])

  if (missing) {
    return (
      <section className="panel eval">
        <div className="panel-head"><h2><FlaskConical size={17} aria-hidden /> Evaluation</h2></div>
        <p className="a-sub pad">No evaluation yet. Run <code>python scripts/07_evaluate.py</code>.</p>
      </section>
    )
  }
  if (!ev) return null
  const s = ev.summary
  const o = ev.offline

  return (
    <section className="panel eval">
      <div className="panel-head">
        <h2><FlaskConical size={17} aria-hidden /> Evaluation: scripted shopping goals</h2>
        <span className="a-sub">Run {ev.generated} · {s.models_used.join(', ')}</span>
      </div>
      <div className="metrics">
        <Metric label="Task success" value={`${s.goals_succeeded}/${s.goals_completed}`}
          note={`${s.checks_passed}/${s.checks_total} checks passed`} />
        <Metric label="Grounding accuracy" value={`${s.grounding_accuracy_pct}%`}
          note={`${s.values_audited} ₹/aisle values audited in ${s.turns} replies`} />
        <Metric label="Discount captured" value={`${s.discount_captured_pct}%`}
          note={`of the brute-force optimum · ${o.carts} random carts: ${o.system_captured_pct}%`} />
        <Metric label="Substitution correct" value={`${s.substitution_correct_pct}%`}
          note={`${s.substitution_cases} unavailable items · top-ranked ${s.substitute_top1_pct}%`} />
        <Metric label="Latency per turn" value={`${s.latency_median_s} s`}
          note={`median · max ${s.latency_max_s} s · ${s.llm_calls_per_turn} LLM calls/turn`} />
        <Metric label="Coupon optimizer" value={`${o.optimizer_ms_median} ms`}
          note={`greedy ${o.greedy_captured_pct}% · one coupon ${o.single_coupon_captured_pct}%`} />
      </div>
      <div className="table-wrap">
        <table className="atable">
          <thead>
            <tr><th>Goal</th><th>Tests</th><th>Result</th><th>Grounded</th><th className="num">Time</th>
              <th className="num">Total</th><th className="num">Discount / optimum</th></tr>
          </thead>
          <tbody>
            {ev.goals.map((g) => (
              <tr key={g.id}>
                <td><div className="a-name">{g.id} · {g.title}</div>
                  {g.failed.length > 0 && <div className="a-sub">Missed: {g.failed.join('; ')}</div>}</td>
                <td className="a-sub">{g.features.join(', ')}</td>
                <td>{g.infra_error ? <span className="a-sub">rate-limited</span>
                  : g.success ? <CheckCircle2 size={17} className="ok-icon" aria-label="success" />
                    : <XCircle size={17} className="bad-icon" aria-label="failed" />}</td>
                <td>{g.grounded ? <CheckCircle2 size={17} className="ok-icon" aria-label="grounded" />
                  : <XCircle size={17} className="bad-icon" aria-label="ungrounded" />}</td>
                <td className="num a-sub">{g.latency_s} s</td>
                <td className="num">{g.final_total ? rupees(g.final_total) : '–'}</td>
                <td className="num">{g.discount ? `${rupees(g.discount)} / ${rupees(g.optimum ?? '0.00')}` : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
