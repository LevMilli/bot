import { Html } from '@react-three/drei'
import type { BotRow, Desk } from '../types'
import {
  beamColorFor,
  hologramPnl,
  hologramPnlValue,
  money,
  pnlTone,
  statusLabel,
} from '../data/format'

/**
 * Quiet name tag on each tower. Full details live in the Towers dropdown —
 * these stay in-world without crowding the orbit.
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
  const color = beamColorFor(bot.id, index)
  const pnlToneClass = offline ? 'flat' : pnlTone(hologramPnlValue(bot))

  return (
    <Html
      position={[0, height + 0.95, 0]}
      center
      sprite
      distanceFactor={18}
      zIndexRange={[40, 10]}
      style={{ pointerEvents: 'auto' }}
    >
      <button
        type="button"
        className={`holo html-holo tower-holo tower-holo-compact ${offline ? 'offline' : ''}`}
        style={{
          borderColor: color,
          boxShadow: `0 0 12px ${color}40`,
        }}
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
        title={statusLabel(bot)}
      >
        <strong>{bot.name}</strong>
        <span className={`holo-pnl tone-${pnlToneClass}`}>
          {offline ? 'offline' : hologramPnl(bot)}
        </span>
        {!offline && (bot.skip_board?.length ?? 0) > 0 && (
          <span className="tower-skips">
            {(bot.skip_board || [])
              .slice(0, 3)
              .map((s) => `${s.code}×${s.n}`)
              .join(' · ')}
          </span>
        )}
      </button>
    </Html>
  )
}

/** Desk vault card — world-anchored above the pad, always screen-facing. */
export function VaultHologram({ desk, workers }: { desk?: Desk; workers: number }) {
  const todayTone = pnlTone(desk?.today)
  const realizedTone = pnlTone(desk?.realized)
  const skips = desk?.more?.skip_leaderboard?.top?.slice(0, 3) || []
  const budgets = desk?.more?.tower_budgets || {}
  const budgetEntries = Object.entries(budgets).slice(0, 4)
  const adapt = desk?.adapt?.by_bot || {}
  let safe = 0
  let big = 0
  for (const row of Object.values(adapt)) {
    safe += Number(row?.safe || 0)
    big += Number(row?.big || 0)
  }
  const tax = desk?.ops?.fill_tax ?? desk?.gate_a?.fill_tax
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
        <strong>THE VAULT · click to enter</strong>
        <span className="holo-pnl">
          <span className={`tone-${realizedTone}`}>realized {money(desk?.realized, true)}</span>
          {' · '}
          <span className={`tone-${todayTone}`}>today {money(desk?.today, true)}</span>
        </span>
        <span>
          cash {money(desk?.cash)} · {workers} worker{workers === 1 ? '' : 's'} on shift
        </span>
        {desk?.pace_line && <span className="holo-pace">{desk.pace_line}</span>}
        {skips.length > 0 && (
          <span className="vault-skips">
            skips {skips.map((s) => `${s.code}×${s.n}`).join(' · ')}
          </span>
        )}
        {budgetEntries.length > 0 && (
          <span className="vault-budgets">
            budgets {budgetEntries.map(([id, n]) => `${id.split('-')[0]} $${Number(n).toFixed(0)}`).join(' · ')}
          </span>
        )}
        {(safe > 0 || big > 0) && (
          <span className="vault-adapt">
            adapt safe×{safe} · big×{big}
          </span>
        )}
        {tax != null && (
          <span className="vault-tax">
            fill tax +{(Number(tax) * 100).toFixed(0)}¢ · taxed ROI is the honest board
          </span>
        )}
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
