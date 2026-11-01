import { flattenTicker, money, pnlTone } from '../data/format'
import type { BotRow } from '../types'

type Props = {
  bots?: BotRow[]
  botId?: string | null
}

export function Ticker({ bots, botId }: Props) {
  const items = flattenTicker(bots, botId)

  if (!items.length) {
    return (
      <div className="ticker" aria-label="Trade ticker">
        <div className="ticker-track">
          <span>No settled paper trades yet — towers are live from pimp_desk.snapshot()</span>
          <span aria-hidden="true">
            No settled paper trades yet — towers are live from pimp_desk.snapshot()
          </span>
        </div>
      </div>
    )
  }

  const row = (
    <>
      {items.map((item, i) => (
        <span key={i} className="ticker-item">
          {item.text}
          {item.pnl != null && (
            <>
              {' '}
              <span className={`tone-${pnlTone(item.pnl)}`}>{money(item.pnl, true)}</span>
            </>
          )}
          {i < items.length - 1 ? '   ✦   ' : ''}
        </span>
      ))}
    </>
  )

  return (
    <div className="ticker" aria-label="Trade ticker">
      <div className="ticker-track">
        <span>{row}</span>
        <span aria-hidden="true">{row}</span>
      </div>
    </div>
  )
}
