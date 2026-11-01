import { Html } from '@react-three/drei'
import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, hologramPnl, money, statusLabel } from '../data/format'

/**
 * Trade labels anchored to each tower.
 * `sprite` keeps the card facing the screen while the city orbits.
 */
export function TowerHologram({
  bot,
  index,
  height,
  onSelect,
}: {
  bot: BotRow
  index: number
  height: number
  onSelect: (id: string) => void
}) {
  const offline = bot.present === false
  const color = BEAM_COLORS[index % BEAM_COLORS.length]

  return (
    <Html
      position={[0, height + 1.35, 0]}
      center
      sprite
      distanceFactor={14}
      zIndexRange={[40, 10]}
      style={{ pointerEvents: 'auto' }}
    >
      <button
        type="button"
        className={`holo html-holo tower-holo ${offline ? 'offline' : ''}`}
        style={{
          borderColor: color,
          boxShadow: `0 0 18px ${color}55`,
        }}
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
      >
        <strong>{bot.name}</strong>
        <span className="holo-status">{statusLabel(bot)}</span>
        <span className={`holo-pnl tone-${offline ? 'flat' : 'up'}`}>{hologramPnl(bot)}</span>
        {!offline && bot.cash != null && (
          <span className="holo-cash">cash {money(bot.cash)}</span>
        )}
      </button>
    </Html>
  )
}

/** Desk vault card — world-anchored above the pad, always screen-facing. */
export function VaultHologram({ desk, workers }: { desk?: Desk; workers: number }) {
  return (
    <Html
      position={[0, 3.4, 0]}
      center
      sprite
      distanceFactor={16}
      zIndexRange={[35, 5]}
      style={{ pointerEvents: 'none' }}
    >
      <div className="holo html-holo vault-holo">
        <strong>THE VAULT</strong>
        <span className="holo-pnl tone-up">
          realized {money(desk?.realized, true)} · today {money(desk?.today, true)}
        </span>
        <span>
          cash {money(desk?.cash)} · {workers} worker{workers === 1 ? '' : 's'} on shift
        </span>
        {desk?.pace_line && <span className="holo-pace">{desk.pace_line}</span>}
      </div>
    </Html>
  )
}

/** Fixed % overlay removed — labels live on the 3D towers now. */
export function CityHologramLayer(_props: {
  bots: BotRow[]
  desk?: Desk
  onSelect: (id: string) => void
}) {
  return null
}
