import { flattenTicker } from '../data/format'
import type { BotRow } from '../types'

type Props = {
  bots?: BotRow[]
  botId?: string | null
}

export function Ticker({ bots, botId }: Props) {
  const items = flattenTicker(bots, botId)
  const text =
    items.length > 0
      ? items.map((i) => i.text).join('   ✦   ')
      : 'No settled paper trades yet — towers are live from pimp_desk.snapshot()'

  return (
    <div className="ticker" aria-label="Trade ticker">
      <div className="ticker-track">
        <span>{text}</span>
        <span aria-hidden="true">{text}</span>
      </div>
    </div>
  )
}
