import type { DataMode } from '../types'

type Props = {
  mode: DataMode
  paperBanner?: string
  error?: string | null
  onConnect?: () => void
}

export function Banners({ mode, paperBanner, error, onConnect }: Props) {
  const paper =
    paperBanner && paperBanner.length > 110
      ? 'PAPER ONLY. No real money, no Kalshi key, no wallet, no live orders.'
      : paperBanner || 'PAPER ONLY. This desk does not trade real money.'
  const needsStaff = Boolean(error && /→ 40[13]/.test(error))
  return (
    <div className="banners">
      <div className="banner paper">{paper}</div>
      {mode === 'offline' && (
        <div className="banner offline">
          Offline demo — live snapshot unreachable
          {error ? ` (${error})` : ''}. Fixture only; not inventing fills.
          {needsStaff && (
            <div className="banner-actions">
              {onConnect && (
                <button type="button" onClick={onConnect}>
                  Show live desk
                </button>
              )}
              <a href="/staff" target="_blank" rel="noreferrer">
                Staff sign-in
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
