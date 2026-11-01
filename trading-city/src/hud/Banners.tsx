import type { DataMode, RoiSystem } from '../types'

type Props = {
  mode: DataMode
  paperBanner?: string
  error?: string | null
  roi?: RoiSystem | null
}

export function Banners({ mode, paperBanner, error, roi }: Props) {
  const paper =
    paperBanner && paperBanner.length > 110
      ? 'PAPER ONLY. No real money, no Kalshi key, no wallet, no live orders.'
      : paperBanner || 'PAPER ONLY. This desk does not trade real money.'
  const roiText =
    roi?.banner ||
    'ROI SYSTEM (paper). Enter only on edge after costs, inside desk risk budget, with an exit plan.'
  const roiShort =
    roiText.length > 120
      ? 'ROI SYSTEM (paper). Edge after costs · desk risk budget · exit plan before entry.'
      : roiText
  const gaps = (roi?.compliance || []).filter((c) => c && c.ok === false)
  return (
    <div className="banners">
      <div className="banner paper">{paper}</div>
      {roi && (
        <div className={`banner roi ${roi.ok === false ? 'roi-warn' : ''}`}>
          {roiShort}
          {roi.ok === false && gaps.length > 0
            ? ` · gaps: ${gaps.map((g) => g.bot).filter(Boolean).join(', ')}`
            : roi.ok
              ? ' · compliance ok'
              : ''}
        </div>
      )}
      {mode === 'offline' && (
        <div className="banner offline">
          Offline demo — live snapshot unreachable
          {error ? ` (${error})` : ''}. Fixture only; not inventing fills.
        </div>
      )}
    </div>
  )
}
