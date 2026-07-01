import fs from 'fs'
import path from 'path'
import LegalPage from '@/components/LegalPage'

export const metadata = { title: 'Privacy Policy — PapersPod' }

export default function PrivacyPage() {
  const content = fs.readFileSync(
    path.join(process.cwd(), 'content/legal/privacy.md'),
    'utf8'
  )
  return <LegalPage content={content} />
}
