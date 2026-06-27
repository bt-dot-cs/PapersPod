const GRADIENTS_BY_LEVEL: Record<string, [string, string][]> = {
  curious: [
    ['#5ec9c4', '#1a7a76'],
    ['#4db8b0', '#0f6b65'],
    ['#68d4cc', '#237070'],
    ['#7adad0', '#2a8078'],
  ],
  informed: [
    ['#c9956e', '#6b3a1a'],
    ['#d4b067', '#7a5010'],
    ['#a67c52', '#4a2810'],
    ['#c08060', '#6b3018'],
    ['#b8a060', '#5c4010'],
    ['#d4a070', '#8b4820'],
    ['#a07850', '#4a2c10'],
    ['#c0a055', '#6b4808'],
  ],
  expert: [
    ['#9b7fd4', '#4a2d8c'],
    ['#8b6bcc', '#3d1f7a'],
    ['#a888dc', '#56359c'],
    ['#b090e0', '#5e3da8'],
  ],
}

function hash(str: string): number {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

const SIZE_CLASS = {
  xs: 'w-10  h-10  text-base  rounded',
  sm: 'w-14  h-14  text-xl    rounded-lg',
  md: 'w-24  h-24  text-4xl   rounded-xl',
  lg: 'w-40  h-40  text-6xl   rounded-2xl',
}

interface Props {
  episodeId: string
  topic?: string | null
  level?: string | null
  size?: keyof typeof SIZE_CLASS
  className?: string
}

export default function EpisodeCover({ episodeId, topic, level, size = 'md', className = '' }: Props) {
  const key = level?.toLowerCase().replace(/[^a-z]/g, '') ?? ''
  const palette = GRADIENTS_BY_LEVEL[key] ?? GRADIENTS_BY_LEVEL.informed
  const [from, to] = palette[hash(episodeId) % palette.length]
  const initial = (topic ?? episodeId).charAt(0).toUpperCase()

  return (
    <div
      className={`${SIZE_CLASS[size]} flex items-center justify-center font-bold select-none flex-shrink-0 ${className}`}
      style={{
        background: `linear-gradient(135deg, ${from}, ${to})`,
        color: 'rgba(255,255,255,0.90)',
      }}
      aria-hidden="true"
    >
      {initial}
    </div>
  )
}
