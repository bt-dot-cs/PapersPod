'use client'
import { useAuth } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { api } from '@/lib/api'

const today = new Date().toISOString().slice(0, 10)
const twoYearsAgo = new Date(Date.now() - 2 * 365 * 86400 * 1000).toISOString().slice(0, 10)

export default function NewEpisodePage() {
  const { getToken } = useAuth()
  const router = useRouter()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const f = new FormData(e.currentTarget)

    const body = {
      topic:                  f.get('topic') as string,
      disciplines:            (f.get('disciplines') as string).split(',').map((s) => s.trim()).filter(Boolean),
      publication_date_range: [f.get('date_start'), f.get('date_end')],
      max_papers:             Number(f.get('max_papers') ?? 10),
      source:                 'auto',
      focus_mode:             'breadth',
      cross_disciplinary:     false,
      include_preprints:      true,
      user_profile: {
        expertise:     [],
        default_level: f.get('expertise_level') ?? 'intermediate',
      },
    }

    try {
      const token = await getToken()
      const result = await api.createEpisode(body, token ?? '')
      router.push(`/episodes/${result.episode_id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold mb-6">New Episode</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Topic</label>
          <input
            name="topic"
            required
            placeholder="e.g. transformer architectures"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Disciplines (comma-separated)</label>
          <input
            name="disciplines"
            required
            placeholder="e.g. machine learning, neuroscience"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Published after</label>
            <input
              type="date"
              name="date_start"
              defaultValue={twoYearsAgo}
              required
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Published before</label>
            <input
              type="date"
              name="date_end"
              defaultValue={today}
              required
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Expertise level</label>
            <select
              name="expertise_level"
              defaultValue="intermediate"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
            >
              <option value="novice">Novice</option>
              <option value="intermediate">Intermediate</option>
              <option value="expert">Expert</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Max papers</label>
            <input
              type="number"
              name="max_papers"
              defaultValue={10}
              min={1}
              max={30}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg text-sm transition-colors"
        >
          {loading ? 'Submitting…' : 'Generate Episode'}
        </button>
      </form>
    </div>
  )
}
