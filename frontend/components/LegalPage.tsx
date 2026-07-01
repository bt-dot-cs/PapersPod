'use client'

import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'

const components: Components = {
  h1: ({ children }) => (
    <h1 style={{
      fontFamily: "'Spectral', Georgia, serif",
      fontSize: '32px',
      fontWeight: 700,
      color: '#f3ece0',
      marginBottom: '8px',
      marginTop: '0',
      lineHeight: 1.15,
    }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{
      fontFamily: "'Spectral', Georgia, serif",
      fontSize: '22px',
      fontWeight: 600,
      color: '#f3ece0',
      marginTop: '40px',
      marginBottom: '10px',
      lineHeight: 1.2,
      borderBottom: '1px solid rgba(240,225,200,0.08)',
      paddingBottom: '8px',
    }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{
      fontFamily: "'Spectral', Georgia, serif",
      fontSize: '17px',
      fontWeight: 600,
      color: '#e8ddc8',
      marginTop: '28px',
      marginBottom: '8px',
    }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{
      fontSize: '14px',
      lineHeight: 1.75,
      color: '#b8aa96',
      marginBottom: '14px',
      marginTop: '0',
    }}>{children}</p>
  ),
  ul: ({ children }) => (
    <ul style={{
      paddingLeft: '20px',
      marginBottom: '14px',
      marginTop: '0',
    }}>{children}</ul>
  ),
  ol: ({ children }) => (
    <ol style={{
      paddingLeft: '20px',
      marginBottom: '14px',
      marginTop: '0',
    }}>{children}</ol>
  ),
  li: ({ children }) => (
    <li style={{
      fontSize: '14px',
      lineHeight: 1.75,
      color: '#b8aa96',
      marginBottom: '4px',
    }}>{children}</li>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      style={{ color: '#d6a44e', textDecoration: 'underline', textUnderlineOffset: '3px' }}
    >{children}</a>
  ),
  strong: ({ children }) => (
    <strong style={{ color: '#e8ddc8', fontWeight: 600 }}>{children}</strong>
  ),
  em: ({ children }) => (
    <em style={{ color: '#b8aa96', fontStyle: 'italic' }}>{children}</em>
  ),
  hr: () => (
    <hr style={{
      border: 'none',
      borderTop: '1px solid rgba(240,225,200,0.08)',
      margin: '36px 0',
    }} />
  ),
  blockquote: ({ children }) => (
    <blockquote style={{
      borderLeft: '3px solid rgba(214,164,78,0.4)',
      paddingLeft: '16px',
      margin: '16px 0',
      color: '#9a8c76',
      fontStyle: 'italic',
    }}>{children}</blockquote>
  ),
  table: ({ children }) => (
    <div style={{ overflowX: 'auto', marginBottom: '20px' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '13.5px',
      }}>{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead style={{ borderBottom: '1px solid rgba(240,225,200,0.12)' }}>{children}</thead>
  ),
  th: ({ children }) => (
    <th style={{
      textAlign: 'left',
      padding: '8px 12px',
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: '10px',
      letterSpacing: '1px',
      textTransform: 'uppercase',
      color: '#9a8c76',
      fontWeight: 500,
    }}>{children}</th>
  ),
  td: ({ children }) => (
    <td style={{
      padding: '8px 12px',
      color: '#b8aa96',
      borderBottom: '1px solid rgba(240,225,200,0.05)',
      verticalAlign: 'top',
      lineHeight: 1.6,
    }}>{children}</td>
  ),
  code: ({ children }) => (
    <code style={{
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: '12px',
      background: 'rgba(240,225,200,0.07)',
      padding: '2px 6px',
      borderRadius: '4px',
      color: '#d6a44e',
    }}>{children}</code>
  ),
}

export default function LegalPage({ content, lastUpdated }: { content: string; lastUpdated?: string }) {
  // Strip the markdown comment lines (used for TODO reminders) before rendering
  const cleaned = content
    .split('\n')
    .filter(line => !line.startsWith('[//]: #'))
    .join('\n')

  return (
    <div style={{
      maxWidth: '740px',
      margin: '0 auto',
      padding: '48px 32px 80px',
    }}>
      {lastUpdated && (
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '10px',
          letterSpacing: '1.2px',
          textTransform: 'uppercase',
          color: '#6a5f52',
          marginBottom: '32px',
        }}>
          Last updated: {lastUpdated}
        </div>
      )}
      <ReactMarkdown components={components}>{cleaned}</ReactMarkdown>
    </div>
  )
}
