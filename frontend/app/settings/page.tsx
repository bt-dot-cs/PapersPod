'use client'
import { api, type ApiKeyInfo } from '@/lib/api'
import { useAuth } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

const PROVIDERS: { id: 'anthropic' | 'openai' | 'gemini'; label: string; description: string }[] = [
  { id: 'anthropic', label: 'Anthropic', description: 'Script generation, bibliography, reasoning, graph extraction' },
  { id: 'openai',    label: 'OpenAI',    description: 'Voice synthesis (TTS) and semantic embeddings' },
  { id: 'gemini',    label: 'Gemini',    description: 'Alternative LLM provider for any pipeline stage' },
]

type Msg = { type: 'success' | 'error'; text: string }

export default function SettingsPage() {
  const { getToken, isSignedIn } = useAuth()
  const [keys, setKeys]       = useState<ApiKeyInfo[]>([])
  const [inputs, setInputs]   = useState<Record<string, string>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [msgs, setMsgs]       = useState<Record<string, Msg>>({})

  useEffect(() => {
    if (!isSignedIn) return
    getToken().then(token => {
      if (!token) return
      api.getApiKeys(token)
        .then(data => setKeys(data.keys))
        .catch(() => {})
    })
  }, [isSignedIn, getToken])

  function keyFor(provider: string): ApiKeyInfo | undefined {
    return keys.find(k => k.provider === provider && k.active)
  }

  function setMsg(provider: string, msg: Msg) {
    setMsgs(prev => ({ ...prev, [provider]: msg }))
    setTimeout(() => setMsgs(prev => { const n = { ...prev }; delete n[provider]; return n }), 4000)
  }

  async function save(provider: string) {
    const val = (inputs[provider] ?? '').trim()
    if (!val) return
    setLoading(prev => ({ ...prev, [provider]: true }))
    try {
      const token = await getToken()
      if (!token) throw new Error('Not signed in')
      const result = await api.upsertApiKey(provider, val, token)
      setKeys(prev => {
        const filtered = prev.filter(k => k.provider !== provider)
        return [...filtered, { provider, key_hint: result.key_hint, active: true }]
      })
      setInputs(prev => ({ ...prev, [provider]: '' }))
      setMsg(provider, { type: 'success', text: `Key saved — ${result.key_hint}` })
    } catch (err) {
      setMsg(provider, { type: 'error', text: err instanceof Error ? err.message : 'Save failed' })
    } finally {
      setLoading(prev => ({ ...prev, [provider]: false }))
    }
  }

  async function remove(provider: string) {
    setLoading(prev => ({ ...prev, [provider]: true }))
    try {
      const token = await getToken()
      if (!token) throw new Error('Not signed in')
      await api.deleteApiKey(provider, token)
      setKeys(prev => prev.filter(k => k.provider !== provider))
      setMsg(provider, { type: 'success', text: 'Key removed' })
    } catch (err) {
      setMsg(provider, { type: 'error', text: err instanceof Error ? err.message : 'Remove failed' })
    } finally {
      setLoading(prev => ({ ...prev, [provider]: false }))
    }
  }

  if (!isSignedIn) {
    return (
      <div style={{ padding: '30px 32px 60px' }}>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Sign in to manage your API keys.</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '30px 32px 60px', maxWidth: '640px' }}>
      <div style={{ fontFamily: "'Spectral', Georgia, serif", fontSize: '30px', fontWeight: 600, margin: '2px 0 4px', color: '#f3ece0' }}>
        API Keys
      </div>
      <div style={{ fontSize: '14px', color: '#ab9f8e', marginBottom: '32px', lineHeight: 1.5 }}>
        Use your own API keys to bypass the credit system. Episodes run with your key cost 0 credits.
      </div>

      {PROVIDERS.map(({ id, label, description }) => {
        const active = keyFor(id)
        const busy   = loading[id] ?? false
        const msg    = msgs[id]
        const input  = inputs[id] ?? ''

        return (
          <div
            key={id}
            style={{
              background: '#1b1611',
              border: '1px solid rgba(240,225,200,0.06)',
              borderRadius: '12px',
              padding: '20px',
              marginBottom: '16px',
            }}
          >
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px', letterSpacing: '1.4px', textTransform: 'uppercase', color: '#9a8c76' }}>
                {label}
              </div>
              {active ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#7bae8f', display: 'inline-block' }} />
                  <span style={{ fontSize: '11px', color: '#7bae8f', fontFamily: "'IBM Plex Mono', monospace" }}>
                    {active.key_hint}
                  </span>
                </div>
              ) : (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}>
                  No key
                </span>
              )}
            </div>

            <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: 1.4 }}>
              {description}
            </div>

            {/* Input row */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="password"
                placeholder={active ? 'Replace existing key…' : 'Paste API key…'}
                value={input}
                onChange={e => setInputs(prev => ({ ...prev, [id]: e.target.value }))}
                onKeyDown={e => { if (e.key === 'Enter') save(id) }}
                style={{
                  flex: 1,
                  padding: '9px 12px',
                  background: '#14110d',
                  border: '1px solid rgba(240,225,200,0.1)',
                  borderRadius: '8px',
                  color: '#f3ece0',
                  fontSize: '13px',
                  fontFamily: "'IBM Plex Mono', monospace",
                  outline: 'none',
                  minWidth: 0,
                }}
              />
              <button
                onClick={() => save(id)}
                disabled={busy || !input}
                style={{
                  padding: '9px 16px',
                  borderRadius: '8px',
                  background: input ? '#d6a44e' : 'rgba(214,164,78,0.2)',
                  color: input ? '#14110d' : '#9a8c76',
                  fontSize: '13px',
                  fontWeight: 600,
                  border: 'none',
                  cursor: input && !busy ? 'pointer' : 'default',
                  flexShrink: 0,
                  opacity: busy ? 0.5 : 1,
                }}
              >
                {busy ? '…' : 'Save'}
              </button>
              {active && (
                <button
                  onClick={() => remove(id)}
                  disabled={busy}
                  style={{
                    padding: '9px 14px',
                    borderRadius: '8px',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    fontSize: '13px',
                    border: '1px solid rgba(240,225,200,0.1)',
                    cursor: busy ? 'default' : 'pointer',
                    flexShrink: 0,
                    opacity: busy ? 0.5 : 1,
                  }}
                >
                  Remove
                </button>
              )}
            </div>

            {/* Inline message */}
            {msg && (
              <div style={{ marginTop: '10px', fontSize: '12px', color: msg.type === 'success' ? '#7bae8f' : '#d4715b' }}>
                {msg.text}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
