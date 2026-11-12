import { useEffect, useId, useRef, useState } from 'react'
import {
  beamColorFor,
  towerClosed,
  hologramPnl,
  hologramPnlValue,
  money,
  pnlTone,
  statusLabel,
} from '../data/format'
import { isResearchTower, isStaffSupport, isSupportTower } from '../data/floorMap'
import type { BotRow } from '../types'

type Props = {
  bots: BotRow[]
  onSelect: (id: string) => void
}

/** A zero or missing realized figure is an empty book, not a result. */
function bookPnlApplies(bot: BotRow): boolean {
  if ((bot.open_count || 0) > 0) return true
  if (bot.history?.length || bot.trades?.length) return true
  if (bot.today != null && Number(bot.today) !== 0) return true
  if (bot.realized != null && Number(bot.realized) !== 0) return true
  return false
}

/** Support sleeves often have no paper book. Say what they are waiting on. */
function supportHeadline(bot: BotRow): string {
  const raw = statusLabel(bot)
  const low = raw.toLowerCase()
  if (low.includes('odds_api_key')) return 'Waiting on Odds API key'
  if (low.includes('sharp')) return 'Waiting on sharp quotes'
  if (low.includes('fed quotes') || low.includes('fedwatch') || low.includes('fed watch')) return 'Waiting on Fed quotes'
  const cleaned = raw
    .replace(/\s*\(no invent\)\s*/gi, '')
    .replace(/\.json\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || 'No paper book yet'
}

function TowerGroup({
  label,
  bots,
  all,
  onSelect,
}: {
  label: string
  bots: BotRow[]
  all: BotRow[]
  onSelect: (id: string) => void
}) {
  if (!bots.length) return null
  return (
    <section className="tower-menu-group" aria-label={label}>
      <h3 className="tower-menu-heading">{label}</h3>
      <ul className="tower-menu-list">
        {bots.map((bot) => (
          <TowerTab key={bot.id} bot={bot} index={Math.max(0, all.indexOf(bot))} onSelect={onSelect} />
        ))}
      </ul>
    </section>
  )
}

function TowerTab({
  bot,
  index,
  onSelect,
}: {
  bot: BotRow
  index: number
  onSelect: (id: string) => void
}) {
  const color = beamColorFor(bot.id, index)
  const closed = towerClosed(bot)
  const status = statusLabel(bot)
  const staff = isStaffSupport(bot.id)
  const supportIdle = (isResearchTower(bot.id) || staff) && !closed && !bookPnlApplies(bot)
  const tone = closed || supportIdle ? 'flat' : pnlTone(hologramPnlValue(bot))
  const desks = bot.traders && bot.traders >= 100 ? bot.traders : 120
  const figure = closed
    ? 'closed'
    : staff
      ? `6 desks · ${desks}`
      : supportIdle
        ? supportHeadline(bot)
        : hologramPnl(bot)
  return (
    <li>
      <button
        type="button"
        className={`tower-tab ${closed ? 'closed' : ''}`}
        style={{ ['--tab-beam' as string]: closed ? '#243044' : color }}
        onClick={() => onSelect(bot.id)}
        title={status}
      >
        <span className="tower-tab-beam" aria-hidden />
        <span className="tower-tab-body">
          <span className="tower-tab-name">{bot.name}</span>
          <span className="tower-tab-meta">
            <span className={supportIdle ? 'tower-tab-pnl tower-tab-wait' : `tower-tab-pnl tone-${tone}`}>
              {figure}
            </span>
            {!supportIdle && !closed && bot.open_count != null && bot.open_count > 0 && (
              <span className="tower-tab-open">open {bot.open_count}</span>
            )}
            {!supportIdle && !closed && bot.cash != null && (
              <span className="tower-tab-cash">{money(bot.cash)}</span>
            )}
          </span>
          {!supportIdle && <span className="tower-tab-status">{status}</span>}
          {staff && !closed && <span className="tower-tab-status">One book. It does not trade.</span>}
        </span>
      </button>
    </li>
  )
}

/**
 * Compact tower dropdown — keeps the plaza clear.
 * World holograms stay as quiet name tags; this menu is the accessible hit target.
 */
export function TowerRail({ bots, onSelect }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onPointer = (e: MouseEvent | PointerEvent) => {
      const el = rootRef.current
      if (el && e.target instanceof Node && !el.contains(e.target)) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  if (!bots.length) return null

  const live = bots.filter((b) => !towerClosed(b)).length
  const research = bots.filter((bot) => isSupportTower(bot.id))
  const support = bots.filter((bot) => isStaffSupport(bot.id))
  const trading = bots.filter((bot) => !isResearchTower(bot.id) && !isStaffSupport(bot.id))

  return (
    <div className={`tower-menu ${open ? 'open' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="tower-menu-toggle"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          setOpen((v) => {
            const next = !v
            if (next) window.dispatchEvent(new Event('apex-frame-towers'))
            return next
          })
        }}
      >
        <span className="tower-menu-beams" aria-hidden>
          {bots.map((bot, i) => (
            <i
              key={bot.id}
              style={{ background: towerClosed(bot) ? '#243044' : beamColorFor(bot.id, i) }}
            />
          ))}
        </span>
        <span className="tower-menu-copy">
          <strong>Towers</strong>
          <em>
            {live}/{bots.length} live
          </em>
        </span>
        <span className="tower-menu-caret" aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>

      {open && (
        <nav className="tower-menu-panel" aria-label="Paper towers" id={listId}>
          <TowerGroup
            label="Trading"
            bots={trading}
            all={bots}
            onSelect={(id) => {
              setOpen(false)
              onSelect(id)
            }}
          />
          <TowerGroup
            label="Research"
            bots={research}
            all={bots}
            onSelect={(id) => {
              setOpen(false)
              onSelect(id)
            }}
          />
          <TowerGroup
            label="Support"
            bots={support}
            all={bots}
            onSelect={(id) => {
              setOpen(false)
              onSelect(id)
            }}
          />
        </nav>
      )}
    </div>
  )
}
