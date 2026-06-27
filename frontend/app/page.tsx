import { auth } from '@clerk/nextjs/server'
import type { Episode, LibraryEpisode } from '@/lib/api'
import { api } from '@/lib/api'
import EpisodeCover from '@/components/EpisodeCover'
import LevelTag from '@/components/LevelTag'
import Link from 'next/link'

export const dynamic = 'force-dynamic'

function epParams(ep: Episode) {
  const p = ep.manifest?.parameters as Record<string, unknown> | undefined
  return {
    topic: p?.topic as string | undefined,
    level: p?.expertise_level as string | undefined,
    field: (p?.disciplines as string[] | undefined)?.[0],
  }
}

function MyEpisodeCard({ ep }: { ep: Episode }) {
  const { topic, level, field } = epParams(ep)
  return (
    <Link
      href={`/episodes/${ep.episode_id}`}
      className="flex-shrink-0 w-40 group"
    >
      <EpisodeCover episodeId={ep.episode_id} topic={topic} level={level} size="md" className="mb-3 group-hover:opacity-90 transition-opacity" />
      <p className="text-sm font-medium leading-snug truncate" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-spectral), Georgia, serif' }}>
        {topic ?? ep.episode_id}
      </p>
      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
        {level && <LevelTag level={level} />}
        {field && <span className="label-caps truncate" style={{ color: 'var(--text-muted)' }}>{field}</span>}
      </div>
    </Link>
  )
}

function CommunityCard({ ep }: { ep: LibraryEpisode }) {
  return (
    <Link
      href={`/episodes/${ep.episode_id}`}
      className="flex-shrink-0 w-40 group"
    >
      <EpisodeCover episodeId={ep.episode_id} topic={ep.topic} size="md" className="mb-3 group-hover:opacity-90 transition-opacity" />
      <p className="text-sm font-medium leading-snug truncate" style={{ color: 'var(--text-primary)' }}>
        {ep.topic}
      </p>
      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
        {ep.listen_count} {ep.listen_count === 1 ? 'listen' : 'listens'}
      </p>
    </Link>
  )
}

function Shelf({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2
        className="text-lg font-semibold mb-4"
        style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-spectral), Georgia, serif' }}
      >
        {title}
      </h2>
      <div className="flex gap-5 overflow-x-auto pb-2" style={{ scrollbarWidth: 'none' }}>
        {children}
      </div>
    </section>
  )
}

export default async function HomePage() {
  const { getToken } = await auth()
  const token = await getToken()

  const [myEpisodes, community] = await Promise.all([
    token ? api.listEpisodes(token).catch(() => [] as Episode[]) : Promise.resolve([] as Episode[]),
    api.getLibrary().catch(() => [] as LibraryEpisode[]),
  ])

  const doneEpisodes = myEpisodes.filter(ep => ep.status === 'done')
  const inProgress   = myEpisodes.filter(ep => ep.status === 'queued' || ep.status === 'running')

  return (
    <div className="space-y-10">
      {inProgress.length > 0 && (
        <section>
          <h2 className="text-base font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>In Progress</h2>
          <div className="space-y-2">
            {inProgress.map(ep => {
              const { topic } = epParams(ep)
              return (
                <Link
                  key={ep.episode_id}
                  href={`/episodes/${ep.episode_id}`}
                  className="flex items-center gap-3 p-3 rounded-lg transition-colors"
                  style={{ background: 'var(--bg-card)' }}
                >
                  <EpisodeCover episodeId={ep.episode_id} topic={topic} size="xs" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                      {topic ?? ep.episode_id}
                    </p>
                    <p className="text-xs capitalize" style={{ color: 'var(--accent)' }}>{ep.status}…</p>
                  </div>
                </Link>
              )
            })}
          </div>
        </section>
      )}

      {doneEpisodes.length > 0 && (
        <Shelf title="My Episodes">
          {doneEpisodes.map(ep => <MyEpisodeCard key={ep.episode_id} ep={ep} />)}
        </Shelf>
      )}

      {community.length > 0 && (
        <Shelf title="Community Library">
          {community.map(ep => <CommunityCard key={ep.episode_id} ep={ep} />)}
        </Shelf>
      )}

      {myEpisodes.length === 0 && community.length === 0 && (
        <div className="py-20 text-center space-y-3">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No episodes yet.</p>
          <Link
            href="/episodes/new"
            className="inline-block text-sm px-4 py-2 rounded-lg transition-colors hover:opacity-80"
            style={{ background: 'var(--accent)', color: 'var(--bg)' }}
          >
            Create your first episode
          </Link>
        </div>
      )}
    </div>
  )
}
