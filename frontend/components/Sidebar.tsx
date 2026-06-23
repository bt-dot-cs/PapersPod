'use client'
import { Show, SignInButton, UserButton } from '@clerk/nextjs'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV = [
  { href: '/',            label: 'Home' },
  { href: '/library',     label: 'Library' },
  { href: '/episodes/new', label: 'New Episode' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="sidebar flex flex-col overflow-y-auto py-6 px-4">
      <div className="px-2 mb-8">
        <span className="text-lg font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
          PapersPod
        </span>
      </div>

      <nav className="flex flex-col gap-0.5 flex-1">
        {NAV.map(({ href, label }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className="px-3 py-2 rounded-md text-sm font-medium transition-colors"
              style={{
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: active ? 'var(--bg-elevated)' : undefined,
              }}
            >
              {label}
            </Link>
          )
        })}
      </nav>

      <div
        className="pt-4 px-2 flex items-center gap-3 mt-4 border-t"
        style={{ borderColor: 'var(--border)' }}
      >
        <Show when="signed-in">
          <UserButton />
        </Show>
        <Show when="signed-out">
          <SignInButton mode="modal">
            <button
              className="text-sm transition-colors hover:opacity-80"
              style={{ color: 'var(--text-secondary)' }}
            >
              Sign in
            </button>
          </SignInButton>
        </Show>
      </div>
    </aside>
  )
}
