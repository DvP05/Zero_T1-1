import { useTidalis } from '../store'

export default function Header() {
  const health = useTidalis((s) => s.health)
  const coastalState = useTidalis((s) => s.coastalState)
  const online = useTidalis((s) => s.online)

  return (
    <header className="topbar">
      <div className="brand">
        <h1>TIDALIS</h1>
        <span className="tagline">AI-Powered Coastal Digital Intelligence</span>
      </div>
      <div className="spacer" />
      <span className={`live-pill ${online ? '' : 'offline'}`}>
        <span className="dot" />
        {online ? 'LIVE' : 'OFFLINE'}
      </span>
      <span className={`status-pill ${coastalState.status}`}>
        {coastalState.status}
      </span>
      <span className="live-pill">
        {health.sensors ?? 0} sensors · {health.events ?? 0} events
      </span>
    </header>
  )
}