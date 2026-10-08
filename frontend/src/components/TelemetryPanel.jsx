import { useTidalis } from '../store'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

export default function TelemetryPanel() {
  const telemetry = useTidalis((s) => s.telemetry)

  if (!telemetry) {
    return (
      <div className="empty-state">
        <p>AWAITING ML TELEMETRY STREAM...</p>
      </div>
    )
  }

  const { model, feature_importance, training_history, drift_report } = telemetry
  const historyPoints = training_history?.points ?? training_history ?? []
  const driftFeatures = drift_report?.features ?? drift_report ?? []
  const simulated = telemetry.simulated_sections ?? []

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', height: '100%' }}>
      
      {/* Left Column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div style={{ borderBottom: '1px solid var(--border-soft)', paddingBottom: '8px' }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
            {model.model_name}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
            LAST TRAINED: {new Date(model.last_trained).toLocaleString()} | SAMPLES: {model.training_samples} | BACKEND: {model.backend}
            {model.measured ? ' | ✓ MEASURED HOLD-OUT METRICS' : ''}
          </div>
        </div>

        <div className="metric-grid">
          <div className="metric">
            <div className="label">Accuracy</div>
            <div className="value good">{(model.accuracy * 100).toFixed(1)}%</div>
          </div>
          <div className="metric">
            <div className="label">F1 Score</div>
            <div className="value">{(model.f1_score * 100).toFixed(1)}%</div>
          </div>
          <div className="metric">
            <div className="label">Precision</div>
            <div className="value">{(model.precision * 100).toFixed(1)}%</div>
          </div>
          <div className="metric">
            <div className="label">Recall</div>
            <div className="value">{(model.recall * 100).toFixed(1)}%</div>
          </div>
          <div className="metric">
            <div className="label">ROC AUC</div>
            <div className="value accent">{(model.auc_roc * 100).toFixed(1)}%</div>
          </div>
          <div className="metric">
            <div className="label">Validation n</div>
            <div className="value">{model.validation_samples}</div>
          </div>
        </div>

        <div style={{ flex: 1, minHeight: '120px' }}>
          <div className="label" style={{ marginBottom: '8px', fontSize: '10px' }}>
            Training History (Loss){training_history?.simulated ? ' · SIMULATED' : ''}
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={historyPoints} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1b2c47" />
              <XAxis dataKey="epoch" tick={{ fill: '#5f7194', fontSize: 10 }} />
              <YAxis tick={{ fill: '#5f7194', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0b1526', borderColor: '#1b2c47', fontSize: '12px' }}
                itemStyle={{ color: '#22d3ee' }}
              />
              <Line type="monotone" dataKey="train_loss" stroke="#22d3ee" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="val_loss" stroke="#fbbf24" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Right Column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', overflowY: 'auto', paddingRight: '4px' }}>
        
        <div>
          <div className="label" style={{ marginBottom: '12px', fontSize: '10px' }}>
            Feature Importance (tree SHAP)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {feature_importance.slice(0, 6).map((f) => (
              <div key={f.feature} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 40px', alignItems: 'center', gap: '10px' }}>
                <div style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--text)' }}>
                  {f.label ?? f.feature.replace(/_/g, ' ')}
                </div>
                <div className="bar-track" style={{ height: '6px', background: 'var(--panel-3)', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, f.importance * 300)}%`, background: 'var(--accent)', borderRadius: '4px' }} />
                </div>
                <div style={{ fontSize: '10px', fontFamily: 'var(--mono)', color: 'var(--accent)', textAlign: 'right' }}>
                  {f.importance.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: '10px' }}>
          <div className="label" style={{ marginBottom: '8px', fontSize: '10px' }}>Data Drift Analysis (PSI){drift_report?.simulated ? ' · SIMULATED' : ''}</div>
          <table className="sim-table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Baseline µ</th>
                <th>Current µ</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {driftFeatures.slice(0, 5).map((d) => (
                <tr key={d.feature}>
                  <td style={{ color: 'var(--text-hi)' }}>{(d.label ?? d.feature).replace(/_/g, ' ')}</td>
                  <td>{d.baseline_mean.toFixed(2)}</td>
                  <td>{d.current_mean.toFixed(2)}</td>
                  <td className={d.status === 'STABLE' ? 'pos' : 'neg'}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {telemetry.confusion_matrix && (
          <div>
            <div className="label" style={{ marginBottom: '8px', fontSize: '10px' }}>
              Confusion Matrix {telemetry.confusion_matrix.measured ? '· MEASURED' : ''}
            </div>
            <div className="metric-grid">
              <div className="metric">
                <div className="label">True Positives</div>
                <div className="value good">{telemetry.confusion_matrix.true_positives}</div>
              </div>
              <div className="metric">
                <div className="label">True Negatives</div>
                <div className="value good">{telemetry.confusion_matrix.true_negatives}</div>
              </div>
              <div className="metric">
                <div className="label">False Positives</div>
                <div className="value warn">{telemetry.confusion_matrix.false_positives}</div>
              </div>
              <div className="metric">
                <div className="label">False Negatives</div>
                <div className="value alert">{telemetry.confusion_matrix.false_negatives}</div>
              </div>
            </div>
          </div>
        )}

        {simulated.length > 0 && (
          <div style={{ fontFamily: 'var(--mono)', fontSize: '9px', letterSpacing: '1.5px', color: 'var(--muted)' }}>
            SIMULATED SECTIONS: {simulated.join(', ').toUpperCase()}
          </div>
        )}
      </div>

    </div>
  )
}
