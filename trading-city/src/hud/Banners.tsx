import type { DataMode } from '../types'

type Props = {
  mode: DataMode
  paperBanner?: string
  error?: string | null
}

export function Banners({ mode, paperBanner, error }: Props) {
  return (
    <div className="banners">
      <div className="banner paper">
        {paperBanner || 'PAPER ONLY. This desk does not trade real money.'}
      </div>
      {mode === 'offline' && (
        <div className="banner offline">
          Offline demo — live snapshot unreachable
          {error ? ` (${error})` : ''}. Showing fixture from last known desk shape; not inventing fills.
        </div>
      )}
    </div>
  )
}
