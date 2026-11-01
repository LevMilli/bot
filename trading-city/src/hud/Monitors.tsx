import type { ReactNode } from 'react'
import type { BotPlans, BotRow, Desk } from '../types'
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

function PlanList({ title, lines }: { title: string; lines?: string[] }) {
  if (!lines?.length) return null
  return (
    <div className="plan-block">
      <strong>{title}</strong>
      <ul>
        {lines.slice(0, 5).map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    </div>
  )
}

function planStake(plans?: BotPlans): string {
  if (!plans?.stake) return ''
  if (plans.stake === 'desk-curve') return 'stake: desk curve'
  if (plans.stake === 'fixed-25') return 'stake: $25 fixed'
  if (plans.stake === 'none') return 'stake: n/a'
  return `stake: ${plans.stake}`
}

function closedTrades(bot: BotRow) {
  return [...(bot.history || []), ...(bot.trades || [])].filter((t) => {
    const side = String(t.side || '').toLowerCase()
    const exit = String(t.exit_reason || t.exit || t.result || '')
    if (side === 'buy') return false
    if (t.pnl != null) return true
    return Boolean(exit) && !/^buy\b/i.test(String(t.what || t.title || ''))
  })
}

/** Live monitor panel bodies — used as Html overlays on 3D screens. */
export function MonitorPanels({ bot, desk }: Props): {
  left: ReactNode
  center: ReactNode
  right: ReactNode
} {
  const positions = bot.positions || []
  const closedPool = closedTrades(bot)
  const last = closedPool.length ? closedPool[closedPool.length - 1] : null
  const series = equitySeries(bot, desk?.curve || desk?.equity)
  const offline = bot.present === false
  const plans = bot.plans
  const gates = bot.gates_hit || []

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
      {gates.length > 0 && <div className="gates-hit">gates: {gates.join(' · ')}</div>}
      <PlanList title="Buy plan" lines={plans?.buy} />
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
        <span>exits {plans?.exit_quality || '—'}</span>
        <span>{planStake(plans)}</span>
        {plans?.entry_gated ? <span>desk entry_gate</span> : null}
        {desk?.ops?.roi_ok === false ? <span className="chip-warn">roi gaps</span> : null}
      </div>
      <PlanList title="Sell plan" lines={plans?.sell} />
    </section>
  )

  const right = (
    <section className="monitor right glass">
      <header>
        <span>stats · failsafes</span>
        <span>{bot.next_run || ''}</span>
      </header>
      <div className={`big-pnl tone-${pnlTone(bot.today)}`}>today {money(bot.today, true)}</div>
      <div className="stat-row">realized {money(bot.realized, true)}</div>
      <div className="stat-row">bankroll {money(bot.cash)}</div>
      {desk?.gate && <div className="warn desk-gate">{desk.gate}</div>}
      <PlanList title="Failsafes" lines={plans?.failsafes} />
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
