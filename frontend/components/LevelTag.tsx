const LEVELS: Record<string, { label: string; color: string; bg: string }> = {
  curious:  { label: 'Curious',  color: '#a8d8a8', bg: 'rgba(168,216,168,0.12)' },
  informed: { label: 'Informed', color: '#d4b067', bg: 'rgba(212,176,103,0.12)' },
  expert:   { label: 'Expert',   color: '#d4a080', bg: 'rgba(212,160,128,0.12)' },
}

interface Props {
  level?: string | null
}

export default function LevelTag({ level }: Props) {
  if (!level) return null
  const key = level.toLowerCase().replace(/[^a-z]/g, '')
  const style = LEVELS[key] ?? {
    label: level,
    color: 'var(--text-secondary)',
    bg: 'var(--bg-elevated)',
  }

  return (
    <span
      className="text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      {style.label}
    </span>
  )
}
