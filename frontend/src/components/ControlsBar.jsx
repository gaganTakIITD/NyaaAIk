const COURTS = [
  { label: 'All Courts', value: 'all' },
  { label: 'Supreme Court', value: 'SC' },
  { label: 'High Courts', value: 'HC' },
  { label: 'District Courts', value: 'DC' },
]
const STYLES = [
  { label: 'Balanced', value: 'neutral' },
  { label: 'In Favour', value: 'favour' },
  { label: 'Against', value: 'against' },
]

export default function ControlsBar({ court, setCourt, style, setStyle }) {
  return (
    <div className="controls-bar" role="toolbar" aria-label="Query settings">
      <div className="control-group">
        <span className="control-label">Court</span>
        {COURTS.map(c => (
          <button
            key={c.value}
            className={`pill${court === c.value ? ' active' : ''}`}
            onClick={() => setCourt(c.value)}
            aria-pressed={court === c.value}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="control-divider" aria-hidden="true" />
      <div className="control-group">
        <span className="control-label">Argument</span>
        {STYLES.map(s => (
          <button
            key={s.value}
            className={`pill${style === s.value ? ' active' : ''}`}
            onClick={() => setStyle(s.value)}
            aria-pressed={style === s.value}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}
