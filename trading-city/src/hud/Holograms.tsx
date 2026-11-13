import { Html } from '@react-three/drei'
import type { BotRow, Desk } from '../types'
import {
  beamColorFor,
  hologramPnl,
  hologramPnlValue,
  money,
  pnlTone,
  statusLabel,
  towerClosed,
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
  shut = false,
}: {
  bot: BotRow
  index: number
  height: number
  onSelect: (id: string) => void
  /** Market closed: grey card, numbers still shown. */
  shut?: boolean
}) {
  const closed = towerClosed(bot)
  const color = beamColorFor(bot.id, index)
  const pnlToneClass = closed ? 'flat' : pnlTone(hologramPnlValue(bot))
  const floorLabel =
    bot.id === 'wall-street'
      ? `6 desks · ${bot.traders && bot.traders >= 100 ? bot.traders : 120}`
      : null

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
        className={`holo html-holo tower-holo tower-holo-compact ${closed ? 'closed' : ''}`}
        style={
          closed
            ? { borderColor: '#243044', boxShadow: 'none' }
            : shut
              ? { borderColor: '#3a4152', boxShadow: 'none', opacity: 0.8 }
              : { borderColor: color, boxShadow: `0 0 12px ${color}40` }
        }
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
        title={statusLabel(bot)}
      >
        <strong>
          {bot.name}
          {shut && <span className="tower-holo-shut"> · closed</span>}
        </strong>
        <span className={`holo-pnl tone-${pnlToneClass}`}>
          {closed ? (bot.present === false ? 'offline' : 'paused') : floorLabel || hologramPnl(bot)}
        </span>
        {!closed && (bot.skip_board?.length ?? 0) > 0 && (
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
  const budgetEntries = Object.entries(budgets)
  const roll = desk?.bankroll
  const deskTowers = roll?.towers?.length
  const shadowTowers = roll?.shadow_towers?.length
  const missing = roll?.missing || []
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
          cash {money(desk?.cash)}
          {deskTowers != null
            ? ` · ${deskTowers} tower${deskTowers === 1 ? '' : 's'} in this cash`
            : ''}
          {' · '}
          {workers} on shift
        </span>
        {shadowTowers != null && shadowTowers > 0 && (
          <span className="vault-books">
            {shadowTowers} shadow tower{shadowTowers === 1 ? '' : 's'} on their own books
            {roll?.shadow_today != null ? ` · today ${money(roll.shadow_today, true)}` : ''}
            {' · not added to this cash'}
          </span>
        )}
        {missing.length > 0 && (
          <span className="vault-books">missing book: {missing.join(', ')}</span>
        )}
        {desk?.pace_line && <span className="holo-pace">{desk.pace_line}</span>}
        {skips.length > 0 && (
          <span className="vault-skips">
            skips {skips.map((s) => `${s.code}×${s.n}`).join(' · ')}
          </span>
        )}
        {budgetEntries.length > 0 && (
          <span className="vault-budgets">
            risk caps {budgetEntries.map(([id, n]) => `${id.split('-')[0]} $${Number(n).toFixed(0)}`).join(' · ')}
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
