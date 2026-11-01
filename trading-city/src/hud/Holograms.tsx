import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, hologramPnl, money, statusLabel, workersOnShift } from '../data/format'
import { RING_R } from '../scene/CityScene'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelect: (id: string) => void
}

/**
 * Screen-space city holograms projected from the same ring math as CityScene.
 * Kept as DOM (not drei Html) so bloom postprocessing cannot clip labels.
 */
export function CityHologramLayer({ bots, desk, onSelect }: Props) {
  const n = Math.max(bots.length, 5)
  const workers = workersOnShift(bots)

  return (
    <div className="holo-layer" aria-label="City holograms">
      {bots.map((bot, i) => {
        const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.12
        // High-angle camera ~[0,15,15] looking at origin — project ring into % space.
        const x = 50 + Math.cos(a) * 28
        const y = 26 + Math.sin(a) * 22
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

      <div className="holo vault-holo" style={{ left: '50%', top: '76%' }}>
        <strong>THE VAULT</strong>
        <span className="holo-pnl tone-up">
          realized {money(desk?.realized, true)} · today {money(desk?.today, true)}
        </span>
        <span>
          cash {money(desk?.cash)} · {workers} worker{workers === 1 ? '' : 's'} on shift
        </span>
        {desk?.pace_line && <span className="holo-pace">{desk.pace_line}</span>}
      </div>
      {/* RING_R referenced so city/HUD stay coupled if ring radius changes */}
      <span hidden>{RING_R}</span>
    </div>
  )
}
