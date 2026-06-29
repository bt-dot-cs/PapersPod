// Aria template's 6 universal gradients — level-independent, assigned by ID hash
const GRADIENTS: [string, string][] = [
  ['#1c2628', '#3a7d78'],
  ['#1c2a1c', '#4f7d4a'],
  ['#221a2e', '#5a4488'],
  ['#241a1a', '#7a4a4a'],
  ['#272016', '#9a7d3a'],
  ['#2c2018', '#8a3b2e'],
]

function idHash(id: string): number {
  return Math.abs(id.split('').reduce((h, c) => (Math.imul(31, h) + c.charCodeAt(0)) | 0, 0))
}

export function episodeGradient(id: string, _level?: string | null): string {
  const [from, to] = GRADIENTS[idHash(id) % GRADIENTS.length]
  return `linear-gradient(150deg, ${from} 0%, ${to} 100%)`
}

export function heroGradient(episodeId: string): string {
  const [, to] = GRADIENTS[idHash(episodeId) % GRADIENTS.length]
  return `linear-gradient(175deg, ${to}55, rgba(20,17,13,0) 90%)`
}

export function levelColor(level?: string | null): string {
  const key = level?.toLowerCase().replace(/[^a-z]/g, '') ?? ''
  const m: Record<string, string> = {
    curious:  '#7bae8f',
    informed: '#d6a44e',
    expert:   '#d4715b',
  }
  return m[key] ?? '#9a8c76'
}
