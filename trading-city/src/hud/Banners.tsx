import type { DataMode } from '../types'

type Props = {
  mode: DataMode
  paperBanner?: string
  error?: string | null
}

export function Banners({ mode, paperBanner, error }: Props) {
  const paper =
    paperBanner && paperBanner.length > 110
      ? 'PAPER ONLY. No real money, no Kalshi key, no wallet, no live orders.'
      : paperBanner || 'PAPER ONLY. This desk does not trade real money.'
  return (
    <div className="banners">
      <div className="banner paper">{paper}</div>
      {mode === 'offline' && (
        <div className="banner offline">
          Offline demo — live snapshot unreachable
          {error ? ` (${error})` : ''}. Fixture only; not inventing fills.
        </div>
      )}
    </div>
  )
}
