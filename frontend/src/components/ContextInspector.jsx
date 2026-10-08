import { useTidalis } from '../store'
import CommandBriefPanel from './CommandBriefPanel'
import PriorityPanel from './PriorityPanel'
import ZoneIntelPanel from './ZoneIntelPanel'
import EventPanel from './EventPanel'

const TABS = [
  { id: 'brief', label: 'Brief', icon: '🧠', title: 'Command Brief (GenAI)' },
  { id: 'priorities', label: 'Priorities', icon: '🎯', title: 'Emergency Priorities' },
  { id: 'zone', label: 'Zone Intel', icon: '🌊', title: 'Zone Intelligence' },
  { id: 'event', label: 'Event', icon: '📍', title: 'Event Details & Evidence' },
]

export default function ContextInspector() {
  const inspectorCollapsed = useTidalis((s) => s.inspectorCollapsed)
  const toggleInspector = useTidalis((s) => s.toggleInspector)
  const setInspectorCollapsed = useTidalis((s) => s.setInspectorCollapsed)
  const inspectorTab = useTidalis((s) => s.inspectorTab)
  const setInspectorTab = useTidalis((s) => s.setInspectorTab)

  if (inspectorCollapsed) {
    return (
      <aside className="context-inspector collapsed">
        <button
          type="button"
          className="inspector-icon-btn expand-toggle"
          onClick={toggleInspector}
          title="Expand Intelligence Inspector"
        >
          ◀
        </button>

        <div className="inspector-icons">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`inspector-icon-btn${inspectorTab === t.id ? ' active' : ''}`}
              onClick={() => {
                setInspectorTab(t.id)
                setInspectorCollapsed(false)
              }}
              title={t.title}
            >
              <span className="icon">{t.icon}</span>
              <span className="icon-label">{t.label}</span>
            </button>
          ))}
        </div>
      </aside>
    )
  }

  return (
    <aside className="context-inspector expanded panel">
      <div className="panel-header inspector-header">
        <div className="inspector-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`inspector-tab-btn${inspectorTab === t.id ? ' active' : ''}`}
              onClick={() => setInspectorTab(t.id)}
              title={t.title}
            >
              <span className="tab-icon">{t.icon}</span>
              <span className="tab-name">{t.label}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          className="collapse-btn"
          onClick={toggleInspector}
          title="Collapse Inspector"
        >
          ▶
        </button>
      </div>

      <div className="panel-body inspector-body">
        {inspectorTab === 'brief' && <CommandBriefPanel />}
        {inspectorTab === 'priorities' && <PriorityPanel />}
        {inspectorTab === 'zone' && <ZoneIntelPanel />}
        {inspectorTab === 'event' && <EventPanel />}
      </div>
    </aside>
  )
}
