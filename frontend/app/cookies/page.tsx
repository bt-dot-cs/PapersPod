import fs from 'fs'
import path from 'path'
import LegalPage from '@/components/LegalPage'

export const metadata = { title: 'Cookie Policy — PapersPod' }

export default function CookiesPage() {
  const content = fs.readFileSync(
    path.join(process.cwd(), 'content/legal/cookies.md'),
    'utf8'
  )
  return <LegalPage content={content} />
}
