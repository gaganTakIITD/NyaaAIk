import { IconMenu, IconClose } from '../utils/icons.jsx'

export default function Topbar({ title, msgCount, onToggleSidebar, sidebarOpen }) {
  return (
    <header className="topbar" id="appTopbar">
      <button
        className="topbar-toggle"
        onClick={onToggleSidebar}
        title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        aria-label="Toggle sidebar"
      >
        {sidebarOpen ? <IconClose size={16} /> : <IconMenu size={16} />}
      </button>

      <div className="topbar-title">
        <h2 title={title}>{title}</h2>
        {msgCount > 0 && (
          <div className="topbar-subtitle">
            {msgCount} message{msgCount !== 1 ? 's' : ''} · Llama 4 Maverick on Databricks
          </div>
        )}
      </div>

      <div className="topbar-actions">
        <div className="status-pill">
          <span className="status-dot" aria-hidden="true" />
          Online
        </div>
      </div>
    </header>
  )
}
