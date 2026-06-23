import { ClerkProvider } from '@clerk/nextjs'
import type { Metadata } from 'next'
import { IBM_Plex_Mono, IBM_Plex_Sans, Spectral } from 'next/font/google'
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
              <main className="main-scroll">{children}</main>
            </div>
            <PlayerBar />
            <NowPlayingOverlay />
          </AudioProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
