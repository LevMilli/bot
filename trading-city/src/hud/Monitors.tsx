import type { ReactNode } from 'react'
import type { BotRow, Desk } from '../types'
import { equitySeries, money, pnlTone, statusLabel } from '../data/format'

type Props = {
  bot: BotRow
  desk?: Desk
}

function Sparkline({ points }: { points: { x: number; y: number }[] }) {
  if (!points.length) {
    return <div className="spark-empty">No closed history yet — waiting on live settles</div>
  }
  const ys = points.map((p) => p.y)
  const min = Math.min(...ys, 0)
  const max = Math.max(...ys, 0)
  const span = max - min || 1
  const w = 280
  const h = 120
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * (w - 8) + 4
      const y = h - 8 - ((p.y - min) / span) * (h - 16)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <path d={d} fill="none" stroke="#f4f7ff" strokeWidth="2.2" />
      <line
        x1="0"
        y1={h - 8 - ((0 - min) / span) * (h - 16)}
        x2={w}
        y2={h - 8 - ((0 - min) / span) * (h - 16)}
        stroke="#f9c80e"
        strokeOpacity="0.5"
        strokeWidth="1"
      />
    </svg>
  )
}

/** Live monitor panel bodies — used as Html overlays on 3D screens. */
export function MonitorPanels({ bot, desk }: Props): {
  left: ReactNode
  center: ReactNode
  right: ReactNode
} {
  const positions = bot.positions || []
  const last =
    (bot.trades && bot.trades[bot.trades.length - 1]) ||
    (bot.history && bot.history[bot.history.length - 1]) ||
    null
  const series = equitySeries(bot, desk?.curve || desk?.equity)
  const offline = bot.present === false

  const left = (
    <section className="monitor left glass">
      <header>
        <span>{bot.status || 'status'}</span>
        <span>{bot.paused ? 'paused' : bot.feed || 'feed'}</span>
      </header>
      <p className="why">{statusLabel(bot)}</p>
      {bot.warning && <p className="warn">{bot.warning}</p>}
      <div className="risk">
        open {bot.open_count ?? 0} · risk {money(bot.open_risk)} · cash {money(bot.cash)}
      </div>
      <ul className="pos-list">
        {offline && <li className="muted">{bot.empty || 'Not on this checkout.'}</li>}
        {!offline && positions.length === 0 && <li className="muted">No open paper positions</li>}
        {positions.slice(0, 8).map((p, i) => (
          <li key={i}>
            <strong>{p.what || p.title || p.team || p.ticker || 'position'}</strong>
            <span>{p.detail || p.game || ''}</span>
            <span>
              {p.side || ''} {money(p.cost)}{' '}
              {p.fill != null ? `@ ${p.fill}` : p.ask != null ? `ask ${p.ask}` : ''}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )

  const center = (
    <section className="monitor center glass">
      <header>
        <span>
          {(bot.positions && bot.positions[0]?.ticker) ||
            (bot.positions && bot.positions[0]?.team) ||
            bot.name}{' '}
          · equity
        </span>
        <span>{bot.central_check || bot.last_check || '—'}</span>
      </header>
      <Sparkline points={series} />
      <div className="chips">
        <span>history {bot.history?.length ?? 0}</span>
        <span>VWAP/EMA cosmetic</span>
      </div>
    </section>
  )

  const right = (
    <section className="monitor right glass">
      <header>
        <span>stats</span>
        <span>{bot.next_run || ''}</span>
      </header>
      <div className={`big-pnl tone-${pnlTone(bot.today)}`}>today {money(bot.today, true)}</div>
      <div className="stat-row">realized {money(bot.realized, true)}</div>
      <div className="stat-row">bankroll {money(bot.cash)}</div>
      <div className="last-trade">
        <strong>Last settled</strong>
        {last ? (
          <>
            <span>{last.what || last.title || last.team || last.ticker || 'trade'}</span>
            <span className={`tone-${pnlTone(last.pnl)}`}>{money(last.pnl, true)}</span>
            <span>{last.result || last.exit_reason || last.exit || ''}</span>
            <span>{last.when || last.closed_at || last.closed || ''}</span>
          </>
        ) : (
          <span className="muted">No closed paper trades yet</span>
        )}
      </div>
    </section>
  )

  return { left, center, right }
}

/** Flat HUD fallback (not used when panels are pinned to 3D monitors). */
export function Monitors({ bot, desk }: Props) {
  const panels = MonitorPanels({ bot, desk })
  return (
    <div className="monitors">
      {panels.left}
      {panels.center}
      {panels.right}
    </div>
  )
}
