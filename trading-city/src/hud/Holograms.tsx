import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, hologramPnl, money, statusLabel, workersOnShift } from '../data/format'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelect: (id: string) => void
}

/** Screen-space city holograms. Angles match CityScene ring (+0.12 offset). */
export function CityHologramLayer({ bots, desk, onSelect }: Props) {
  const n = Math.max(bots.length, 5)
  const workers = workersOnShift(bots)

  return (
    <div className="holo-layer" aria-label="City holograms">
      {bots.map((bot, i) => {
        const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.12
        // Project ring into the tighter high-angle frame.
        // Push labels slightly outward from beams so text stays readable.
        const x = 50 + Math.cos(a) * 30
        const y = 30 + Math.sin(a) * 24
        const offline = bot.present === false
        return (
          <button
            key={bot.id}
            type="button"
            className={`holo tower-holo ${offline ? 'offline' : ''}`}
            style={{
              left: `${x}%`,
              top: `${y}%`,
              borderColor: BEAM_COLORS[i % BEAM_COLORS.length],
              boxShadow: `0 0 18px ${BEAM_COLORS[i % BEAM_COLORS.length]}55`,
            }}
            onClick={() => onSelect(bot.id)}
          >
            <strong>{bot.name}</strong>
            <span className="holo-status">{statusLabel(bot)}</span>
            <span className={`holo-pnl tone-${offline ? 'flat' : 'up'}`}>{hologramPnl(bot)}</span>
            {!offline && bot.cash != null && (
              <span className="holo-cash">cash {money(bot.cash)}</span>
            )}
          </button>
        )
      })}

      <div className="holo vault-holo" style={{ left: '50%', top: '78%' }}>
        <strong>THE VAULT</strong>
        <span>
          realized {money(desk?.realized, true)} · today {money(desk?.today, true)}
        </span>
        <span>
          cash {money(desk?.cash)} · {workers} worker{workers === 1 ? '' : 's'} on shift
        </span>
        {desk?.pace_line && <span className="holo-pace">{desk.pace_line}</span>}
      </div>
    </div>
  )
}
