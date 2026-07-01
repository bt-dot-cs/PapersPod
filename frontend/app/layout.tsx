import { ClerkProvider } from '@clerk/nextjs'
import type { Metadata } from 'next'
import { IBM_Plex_Mono, IBM_Plex_Sans, Spectral } from 'next/font/google'
import Link from 'next/link'
import NowPlayingOverlay from '@/components/NowPlayingOverlay'
import PlayerBar from '@/components/PlayerBar'
import Sidebar from '@/components/Sidebar'
import { AudioProvider } from '@/contexts/AudioContext'
import './globals.css'

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-ibm-plex-sans',
})

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-ibm-plex-mono',
})

const spectral = Spectral({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  style: ['normal', 'italic'],
  variable: '--font-spectral',
})

export const metadata: Metadata = {
  title: 'PapersPod',
  description: 'Research papers as podcasts',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        className={`${ibmPlexSans.variable} ${ibmPlexMono.variable} ${spectral.variable}`}
      >
        <body>
          <AudioProvider>
            <div className="app-shell">
              <Sidebar />
              <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', flex: 1, overflow: 'hidden' }}>
                <main className="main-scroll" style={{ flex: 1 }}>{children}</main>
                <footer style={{
                  display: 'flex',
                  gap: '20px',
                  padding: '16px 32px',
                  borderTop: '1px solid rgba(240,225,200,0.06)',
                  flexShrink: 0,
                }}>
                  {[
                    { href: '/terms', label: 'Terms' },
                    { href: '/privacy', label: 'Privacy' },
                    { href: '/cookies', label: 'Cookies' },
                  ].map(({ href, label }) => (
                    <Link
                      key={href}
                      href={href}
                      style={{
                        fontFamily: "'IBM Plex Mono', monospace",
                        fontSize: '10px',
                        letterSpacing: '1px',
                        textTransform: 'uppercase',
                        color: '#6a5f52',
                        textDecoration: 'none',
                      }}
                    >
                      {label}
                    </Link>
                  ))}
                </footer>
              </div>
            </div>
            <PlayerBar />
            <NowPlayingOverlay />
          </AudioProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
