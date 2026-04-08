import { IconMenu, IconClose } from '../utils/icons.jsx'

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="12" cy="12" r="4"/>
      <line x1="12" y1="2" x2="12" y2="5"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
      <line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/>
      <line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/>
      <line x1="2" y1="12" x2="5" y2="12"/>
      <line x1="19" y1="12" x2="22" y2="12"/>
      <line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/>
      <line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/>
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  )
}

export default function Topbar({ title, msgCount, onToggleSidebar, sidebarOpen, theme, onToggleTheme }) {
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
        {/* Theme toggle */}
        <button
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-label="Toggle theme"
          id="themeToggleBtn"
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>

        <div className="status-pill">
          <span className="status-dot" aria-hidden="true" />
          Online
        </div>
      </div>
    </header>
  )
}
