import fs from 'fs'
import path from 'path'
import LegalPage from '@/components/LegalPage'

export const metadata = { title: 'Terms of Service — PapersPod' }

export default function TermsPage() {
  const content = fs.readFileSync(
    path.join(process.cwd(), 'content/legal/terms.md'),
    'utf8'
  )
  return <LegalPage content={content} />
}
