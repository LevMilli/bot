import { useEffect, useId, useRef, useState } from 'react'
import {
  beamColorFor,
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

  const live = bots.filter((b) => b.present !== false).length

  return (
    <div className={`tower-menu ${open ? 'open' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="tower-menu-toggle"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="tower-menu-beams" aria-hidden>
          {bots.slice(0, 6).map((bot, i) => (
            <i key={bot.id} style={{ background: beamColorFor(bot.id, i) }} />
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
          <ul className="tower-menu-list">
            {bots.map((bot, i) => {
              const color = beamColorFor(bot.id, i)
              const offline = bot.present === false
              const tone = offline ? 'flat' : pnlTone(hologramPnlValue(bot))
              const status = statusLabel(bot)
              return (
                <li key={bot.id}>
                  <button
                    type="button"
                    className={`tower-tab ${offline ? 'offline' : ''}`}
                    style={{ ['--tab-beam' as string]: color }}
                    onClick={() => {
                      setOpen(false)
                      onSelect(bot.id)
                    }}
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
      )}
    </div>
  )
}
