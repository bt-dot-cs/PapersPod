const LEVELS: Record<string, { label: string; color: string; bg: string }> = {
  curious:  { label: 'Curious',  color: 'var(--level-curious)',  bg: 'var(--level-curious-bg)' },
  informed: { label: 'Informed', color: 'var(--level-informed)', bg: 'var(--level-informed-bg)' },
  expert:   { label: 'Expert',   color: 'var(--level-expert)',   bg: 'var(--level-expert-bg)' },
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
      className="label-caps px-2 py-0.5 rounded-full"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      {style.label}
    </span>
  )
}
