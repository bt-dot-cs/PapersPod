const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

async function req<T>(path: string, token?: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

export interface EpisodeSegment {
  start: number        // seconds
  end: number          // seconds
  paper_refs: string[] // arXiv IDs
}

export interface Episode {
  episode_id: string
  status: 'queued' | 'planning' | 'building' | 'running' | 'done' | 'failed'
  created_at: string
  completed_at?: string
  error?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  manifest?: Record<string, any>
  shared: boolean
  is_owner?: boolean
}

export interface LibraryEpisode {
  episode_id: string
  topic: string
  created_at: string
  completed_at?: string
  shared_at?: string
  listen_count: number
  avg_completion_pct?: number
}

export interface Paper {
  arxiv_id: string
  doi?: string
  title: string
  authors: string[]
  published_date?: string
  annotation?: string
}

export interface CreateEpisodeResult {
  episode_id: string
  status: string
}

export interface CostEvent {
  episode_id: string
  created_at?: string
  topic?: string
  source?: string
  expertise_level?: string
  max_papers?: number
  anchor_paper?: string
  tokens_input?: number
  tokens_output?: number
  cost_claude_input?: number
  cost_claude_output?: number
  cost_claude?: number
  cost_tts?: number
  cost_total?: number
  tts_provider_requested?: string
  tts_provider_used?: string
  tts_fallback_occurred?: boolean
  tts_characters?: number
  runtime_seconds?: number
  warnings?: unknown
}

export interface CreditsBalance {
  balance: number
}

export interface ApiKeyInfo {
  provider: string
  key_hint: string
  active: boolean
  created_at?: string
  last_used_at?: string
}

export interface FeedbackResult {
  credits_granted: number
  new_balance: number
  throttled: boolean
}

export const api = {
  getCredits:    (token: string) => req<CreditsBalance>('/credits', token),
  getApiKeys:    (token: string) => req<{ keys: ApiKeyInfo[] }>('/settings/api-keys', token),
  upsertApiKey:  (provider: string, apiKey: string, token: string) =>
    req<{ provider: string; key_hint: string; active: boolean }>(`/settings/api-keys/${provider}`, token, {
      method: 'PUT', body: JSON.stringify({ api_key: apiKey }),
    }),
  deleteApiKey:  (provider: string, token: string) =>
    req<{ provider: string; active: boolean }>(`/settings/api-keys/${provider}`, token, { method: 'DELETE' }),
  submitFeedback: (body: { feedback_type: 'bug' | 'improvement' | 'positive'; content: string }, token: string) =>
    req<FeedbackResult>('/credits/feedback', token, { method: 'POST', body: JSON.stringify(body) }),
  listEpisodes:  (token?: string | null) => req<Episode[]>('/episodes', token),
  getEpisode:    (id: string, token?: string | null) => req<Episode>(`/episodes/${id}`, token),
  getAudioUrl:   (id: string) => req<{ url: string }>(`/episodes/${id}/audio-url`),
  createEpisode: (body: Record<string, unknown>, token: string) =>
    req<CreateEpisodeResult>('/episodes', token, { method: 'POST', body: JSON.stringify(body) }),
  shareEpisode:  (id: string, shared: boolean, token: string) =>
    req<null>(`/episodes/${id}/share`, token, { method: 'PATCH', body: JSON.stringify({ shared }) }),
  getLibrary:    () => req<LibraryEpisode[]>('/episodes/library'),
  getRelated:    (id: string) => req<LibraryEpisode[]>(`/episodes/${id}/related`),
  getPapers:     (id: string) => req<Paper[]>(`/episodes/${id}/papers`),
  getAdminCostEvents: (token: string, limit = 50) =>
    req<CostEvent[]>(`/admin/cost-events?limit=${limit}`, token),
  recordPlayEvent: (event: {
    episode_id: string
    event_type: string
    completion_pct?: number
    session_id?: string
  }) => req<null>('/events/play', null, { method: 'POST', body: JSON.stringify(event) }),
}
