import { auth } from '@clerk/nextjs/server'
import type { Episode, LibraryEpisode } from '@/lib/api'
import { api } from '@/lib/api'
import EpisodeCover from '@/components/EpisodeCover'
import Link from 'next/link'
import { episodeGradient, levelColor } from '@/lib/episode-utils'

export const dynamic = 'force-dynamic'

function epParams(ep: Episode) {
  const p = ep.manifest?.parameters as Record<string, unknown> | undefined
  return {
    topic: p?.topic as string | undefined,
    level: p?.expertise_level as string | undefined,
    field: (p?.disciplines as string[] | undefined)?.[0],
  }
}

function LevelTag({ level }: { level: string }) {
  const c = levelColor(level)
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '9.5px',
        letterSpacing: '0.8px',
        textTransform: 'uppercase',
        color: c,
        border: `1px solid ${c}66`,
        background: `${c}1a`,
        padding: '2px 7px',
        borderRadius: '5px',
      }}
    >
      {level}
    </span>
  )
}

function EpisodeCard({ ep }: { ep: Episode }) {
  const { topic, level, field } = epParams(ep)
  const initial = (topic ?? ep.episode_id).charAt(0).toUpperCase()
  const bg = episodeGradient(ep.episode_id, level)

  return (
    <Link href={`/episodes/${ep.episode_id}`} style={{ textDecoration: 'none' }}>
      <div
        style={{
          background: '#1b1611',
          border: '1px solid rgba(240,225,200,0.06)',
          borderRadius: '12px',
          padding: '13px',
          cursor: 'pointer',
          transition: 'background .18s, transform .18s',
          position: 'relative',
        }}
        className="ep-card"
      >
        {/* Cover */}
        <div
          style={{
            aspectRatio: '1',
            borderRadius: '10px',
            background: bg,
            marginBottom: '13px',
            padding: '13px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            boxShadow: '0 8px 24px rgba(0,0,0,0.32)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            {level && <LevelTag level={level} />}
          </div>
          <span
            style={{
              fontFamily: "'Spectral', Georgia, serif",
              fontSize: '46px',
              lineHeight: 1,
              color: 'rgba(255,255,255,0.96)',
              textShadow: '0 2px 12px rgba(0,0,0,0.3)',
            }}
          >
            {initial}
          </span>
        </div>

        {field && (
          <div
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '9.5px',
              letterSpacing: '1.4px',
              textTransform: 'uppercase',
              color: '#9a8c76',
              marginBottom: '5px',
            }}
          >
            {field}
          </div>
        )}

        <div
          style={{
            fontFamily: "'Spectral', Georgia, serif",
            fontSize: '16.5px',
            fontWeight: 600,
            lineHeight: 1.22,
            marginBottom: '6px',
            color: '#f3ece0',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {topic ?? ep.episode_id}
        </div>

        <div style={{ fontSize: '11.5px', color: '#8a7d6a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          PapersPod
        </div>
      </div>
    </Link>
  )
}

function CommunityCard({ ep }: { ep: LibraryEpisode }) {
  const initial = ep.topic.charAt(0).toUpperCase()
  const bg = episodeGradient(ep.episode_id, null)

  return (
    <Link href={`/episodes/${ep.episode_id}`} style={{ textDecoration: 'none' }}>
      <div
        style={{
          background: '#1b1611',
          border: '1px solid rgba(240,225,200,0.06)',
          borderRadius: '12px',
          padding: '13px',
          cursor: 'pointer',
          transition: 'background .18s, transform .18s',
          position: 'relative',
        }}
        className="ep-card"
      >
        <div
          style={{
            aspectRatio: '1',
            borderRadius: '10px',
            background: bg,
            marginBottom: '13px',
            padding: '13px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            boxShadow: '0 8px 24px rgba(0,0,0,0.32)',
          }}
        >
          <span
            style={{
              fontFamily: "'Spectral', Georgia, serif",
              fontSize: '46px',
              lineHeight: 1,
              color: 'rgba(255,255,255,0.96)',
              textShadow: '0 2px 12px rgba(0,0,0,0.3)',
            }}
          >
            {initial}
          </span>
        </div>

        <div
          style={{
            fontFamily: "'Spectral', Georgia, serif",
            fontSize: '16.5px',
            fontWeight: 600,
            lineHeight: 1.22,
            marginBottom: '6px',
            color: '#f3ece0',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {ep.topic}
        </div>

        <div style={{ fontSize: '11.5px', color: '#8a7d6a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {ep.listen_count} {ep.listen_count === 1 ? 'listen' : 'listens'}
        </div>
      </div>
    </Link>
  )
}

function Shelf({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '38px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          marginBottom: '16px',
        }}
      >
        <div
          style={{
            fontFamily: "'Spectral', Georgia, serif",
            fontSize: '21px',
            fontWeight: 600,
            color: '#f3ece0',
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: '11px',
            letterSpacing: '1px',
            color: '#8a7d6a',
            cursor: 'pointer',
          }}
        >
          SEE ALL
        </div>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
          gap: '18px',
        }}
      >
        {children}
      </div>
    </div>
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
    <div style={{ padding: '30px 32px 60px' }}>

      {/* Greeting */}
      <div
        style={{
          fontFamily: "'Spectral', Georgia, serif",
          fontSize: '30px',
          fontWeight: 600,
          margin: '2px 0 4px',
          color: '#f3ece0',
        }}
      >
        Good evening
      </div>
      <div style={{ fontSize: '14px', color: '#ab9f8e', marginBottom: '26px' }}>
        Five papers, one conversation. Pick a thread — or let us surprise you.
      </div>

      {/* Surprise me banner */}
      <Link
        href="/episodes/new"
        style={{ textDecoration: 'none', display: 'block' }}
      >
        <div
          style={{
            position: 'relative',
            overflow: 'hidden',
            borderRadius: '16px',
            padding: '30px 34px',
            marginBottom: '38px',
            background: 'linear-gradient(110deg,#241a10 0%,#3a2614 45%,#1d160e 100%)',
            border: '1px solid rgba(214,164,78,0.28)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
          className="surprise-banner"
        >
          <div style={{ maxWidth: '62%' }}>
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '11px',
                letterSpacing: '2px',
                color: '#d6a44e',
                textTransform: 'uppercase',
                marginBottom: '10px',
              }}
            >
              For the generally curious
            </div>
            <div
              style={{
                fontFamily: "'Spectral', Georgia, serif",
                fontSize: '28px',
                fontWeight: 600,
                lineHeight: 1.15,
                marginBottom: '8px',
                color: '#f3ece0',
              }}
            >
              Learn something you weren&rsquo;t looking for.
            </div>
            <div style={{ fontSize: '13.5px', color: '#bcae99', lineHeight: 1.5 }}>
              Pick a topic, choose your depth, and we&rsquo;ll build you an episode from the latest papers — a contradiction in cosmology, a fight about replication, the bacteria in your gut.
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3,12px)',
                gridTemplateRows: 'repeat(3,12px)',
                gap: '7px',
                padding: '18px',
                background: 'rgba(214,164,78,0.1)',
                borderRadius: '14px',
              }}
            >
              {[1,0,1,0,1,0,1,0,1].map((on, i) => (
                <div
                  key={i}
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    background: on ? '#d6a44e' : 'transparent',
                  }}
                />
              ))}
            </div>
            <div
              style={{
                width: '54px',
                height: '54px',
                borderRadius: '50%',
                background: '#d6a44e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 8px 26px rgba(214,164,78,0.4)',
              }}
            >
              <svg width="18" height="20" viewBox="0 0 18 20" fill="none">
                <path d="M2 1.5L16.5 10 2 18.5V1.5z" fill="#14110d" />
              </svg>
            </div>
          </div>
        </div>
      </Link>

      {/* In-progress */}
      {inProgress.length > 0 && (
        <div style={{ marginBottom: '38px' }}>
          <div
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '9.5px',
              letterSpacing: '1.4px',
              textTransform: 'uppercase',
              color: '#8a7d6a',
              marginBottom: '10px',
            }}
          >
            Generating
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {inProgress.map(ep => {
              const { topic } = epParams(ep)
              return (
                <Link
                  key={ep.episode_id}
                  href={`/episodes/${ep.episode_id}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '14px',
                    padding: '12px 16px', borderRadius: '10px',
                    background: '#1b1611',
                    border: '1px solid rgba(240,225,200,0.06)',
                    textDecoration: 'none',
                  }}
                >
                  <EpisodeCover episodeId={ep.episode_id} topic={topic} size="xs" />
                  <div>
                    <p style={{ fontSize: '14px', fontWeight: 500, color: '#f3ece0' }}>
                      {topic ?? ep.episode_id}
                    </p>
                    <p style={{ fontSize: '12px', color: '#d6a44e', textTransform: 'capitalize' }}>
                      {ep.status}…
                    </p>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      )}

      {/* Shelves */}
      {doneEpisodes.length > 0 && (
        <Shelf title="Continue listening">
          {doneEpisodes.map(ep => <EpisodeCard key={ep.episode_id} ep={ep} />)}
        </Shelf>
      )}
      {community.length > 0 && (
        <Shelf title="From the community">
          {community.map(ep => <CommunityCard key={ep.episode_id} ep={ep} />)}
        </Shelf>
      )}

      {/* Empty state */}
      {myEpisodes.length === 0 && community.length === 0 && (
        <div style={{ paddingTop: '80px', textAlign: 'center' }}>
          <p style={{ fontSize: '14px', color: '#9a8c76', marginBottom: '16px' }}>
            No episodes yet.
          </p>
          <Link
            href="/episodes/new"
            style={{
              display: 'inline-block',
              background: '#d6a44e', color: '#14110d',
              padding: '10px 22px', borderRadius: '8px',
              fontSize: '14px', fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            Create your first episode
          </Link>
        </div>
      )}

      {/* Choose your depth */}
      <div style={{ marginBottom: '14px' }}>
        <div
          style={{
            fontFamily: "'Spectral', Georgia, serif",
            fontSize: '21px',
            fontWeight: 600,
            marginBottom: '6px',
            color: '#f3ece0',
          }}
        >
          Choose your depth
        </div>
        <div style={{ fontSize: '13px', color: '#8a7d6a', marginBottom: '16px' }}>
          Every topic is recorded at three expertise levels. Same papers, different conversation.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          {[
            {
              level: 'Curious',
              color: '#7bae8f',
              border: 'rgba(123,174,143,0.25)',
              desc: 'Story-first and jargon-free. For the commute or the kitchen — no background assumed.',
            },
            {
              level: 'Informed',
              color: '#d6a44e',
              border: 'rgba(214,164,78,0.25)',
              desc: "Assumes general literacy in the field. Methods get discussed; terms aren't over-explained.",
            },
            {
              level: 'Expert',
              color: '#d4715b',
              border: 'rgba(212,113,91,0.25)',
              desc: 'Full technical depth. Caveats, statistical nuance, and expert-level debates included.',
            },
          ].map(({ level, color, border, desc }) => (
            <div
              key={level}
              style={{
                background: '#1b1611',
                border: `1px solid ${border}`,
                borderRadius: '12px',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <div
                  style={{
                    width: '9px',
                    height: '9px',
                    borderRadius: '50%',
                    background: color,
                  }}
                />
                <div style={{ fontWeight: 600, fontSize: '15px', color: '#f3ece0' }}>
                  {level}
                </div>
              </div>
              <div style={{ fontSize: '12.5px', color: '#9a8c76', lineHeight: 1.5 }}>
                {desc}
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
