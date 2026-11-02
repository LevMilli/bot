import {
  BEAM_COLORS,
  hologramPnl,
  hologramPnlValue,
  money,
  pnlTone,
  statusLabel,
} from '../data/format'
import type { BotRow } from '../types'

type Props = {
  bots: BotRow[]
  onSelect: (id: string) => void
}

/**
 * Edge tower tabs — always readable, out of the orbit path.
 * World holograms stay as quiet name tags; this rail is the accessible hit target.
 */
export function TowerRail({ bots, onSelect }: Props) {
  if (!bots.length) return null
  return (
    <nav className="tower-rail" aria-label="Paper towers">
      <div className="tower-rail-label">TOWERS</div>
      <ul className="tower-rail-list">
        {bots.map((bot, i) => {
          const color = BEAM_COLORS[i % BEAM_COLORS.length]
          const offline = bot.present === false
          const tone = offline ? 'flat' : pnlTone(hologramPnlValue(bot))
          const status = statusLabel(bot)
          return (
            <li key={bot.id}>
              <button
                type="button"
                className={`tower-tab ${offline ? 'offline' : ''}`}
                style={{ ['--tab-beam' as string]: color }}
                onClick={() => onSelect(bot.id)}
                title={status}
              >
                <span className="tower-tab-beam" aria-hidden />
                <span className="tower-tab-body">
                  <span className="tower-tab-name">{bot.name}</span>
                  <span className="tower-tab-meta">
                    <span className={`tower-tab-pnl tone-${tone}`}>
                      {offline ? 'offline' : hologramPnl(bot)}
                    </span>
                    {!offline && bot.open_count != null && bot.open_count > 0 && (
                      <span className="tower-tab-open">open {bot.open_count}</span>
                    )}
                    {!offline && bot.cash != null && (
                      <span className="tower-tab-cash">{money(bot.cash)}</span>
                    )}
                  </span>
                  <span className="tower-tab-status">{status}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
