import { useEffect, useMemo, useState } from 'react'
import type { BotRow, Desk, RoiSystem, Snapshot, TradeOrHistory } from '../types'
import { money, statusLabel } from '../data/format'
import { isResearchTower, isStaffSupport } from '../data/floorMap'

const NOTES_KEY = 'apex-city-boss-notes-v1'
const AUTO_LEARN_KEY = 'apex-city-auto-learn-v1'

type StaffNotes = Record<string, string>
type Tab = 'floor' | 'history' | 'learn'
type FloorFilter = 'all' | 'trading' | 'research' | 'support' | 'open' | 'paused'
type HistoryLoad = '60' | '100' | '200' | 'all'

type HistRow = {
  key: string
  botId: string
  botName: string
  when: string
  what: string
  pnl: number | null
  result: string
  at: number
}

function loadNotes(): StaffNotes {
  try {
    return JSON.parse(localStorage.getItem(NOTES_KEY) || '{}') as StaffNotes
  } catch {
    return {}
  }
}

function saveNotes(notes: StaffNotes) {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes))
}

function whenMs(when: string): number {
  const cleaned = when.replace(/\s+(Central|CT|UTC|ET|PT)$/i, '')
  const t = Date.parse(cleaned)
  return Number.isNaN(t) ? 0 : t
}

function historyRows(bot: BotRow): HistRow[] {
  const pool: TradeOrHistory[] = bot.history?.length ? bot.history : bot.trades || []
  return pool.map((row, i) => {
    const when = String(row.when || row.closed_at || row.closed || '')
    const what = String(row.ticker || row.what || row.title || row.team || 'trade')
    const raw = typeof row.pnl === 'number' ? row.pnl : row.pnl == null ? null : Number(row.pnl)
    return {
      key: `${bot.id}-${when}-${what}-${i}`,
      botId: bot.id,
      botName: bot.name,
      when: when || '—',
      what,
      pnl: raw != null && Number.isFinite(raw) ? raw : null,
      result: String(row.result || row.exit_reason || ''),
      at: whenMs(when),
    }
  })
}

function adaptLine(id: string, row: Record<string, unknown>, name: string): string {
  const bits = [name || id]
  if (row.play_safe || row.safe) bits.push('play-safe')
  if (row.play_big || row.big) bits.push('sized up')
  if (typeof row.obs === 'number') bits.push(`${row.obs} obs`)
  if (typeof row.hit === 'number') bits.push(`hit ${Math.round(Number(row.hit) * 100)}%`)
  const notes = row.notes || row.last_notes
  if (Array.isArray(notes) && notes[0]) bits.push(String(notes[0]).slice(0, 90))
  if (typeof row.last_at === 'string' && row.last_at) bits.push(String(row.last_at))
  if (bits.length === 1) bits.push('no adapt flag')
  return bits.join(' · ')
}

function tipForBot(bot: BotRow, adaptBot?: Record<string, unknown>): string[] {
  const tips: string[] = []
  if (bot.paused) tips.push('Bot is paused — resume only when gates and news calendar are clear.')
  if (bot.skip) tips.push(`Last skip: ${bot.skip}`)
  if (bot.why) tips.push(`Why idle: ${bot.why}`)
  if (bot.starve_reason) tips.push(`Starved: ${bot.starve_reason}`)
  if ((bot.expectancy_hit_rate ?? 1) < 0.8 && (bot.expectancy_n ?? 0) >= 8) {
    tips.push('Hit rate under 80% on sample — desk adapt will stay play-safe until proven.')
  }
  if ((bot.open_count ?? 0) > 0 && !(bot.plans?.sell || []).length) {
    tips.push('Open risk without a clear sell plan — confirm settle/TP path.')
  }
  const notes = adaptBot?.notes || adaptBot?.last_notes
  if (Array.isArray(notes)) {
    for (const n of notes.slice(0, 3)) tips.push(`Adapt: ${String(n)}`)
  }
  if (adaptBot?.play_safe) tips.push('Adapt is in play-safe mode (vol / false-confidence / weak record).')
  if (adaptBot?.play_big) tips.push('Adapt sized up — record cleared ≥80% with CI floor.')
  if (!tips.length) tips.push('No hard flags — keep fee-aware entries and let adapt log vol regimes.')
  return tips.slice(0, 6)
}

type Props = {
  bots: BotRow[]
  desk?: Desk
  roi?: RoiSystem
  snap?: Snapshot | null
  onClose: () => void
  onFocusBot: (id: string) => void
}

export function BossDashboard({ bots, desk, roi, snap, onClose, onFocusBot }: Props) {
  const [selectedId, setSelectedId] = useState(bots[0]?.id || '')
  const [notes, setNotes] = useState<StaffNotes>({})
  const [autoLearn, setAutoLearn] = useState(true)
  const [tab, setTab] = useState<Tab>('floor')
  const [historyBot, setHistoryBot] = useState('all')
  const [historyLoad, setHistoryLoad] = useState<HistoryLoad>('60')
  const [floorFilter, setFloorFilter] = useState<FloorFilter>('all')

  useEffect(() => {
    setNotes(loadNotes())
    setAutoLearn(localStorage.getItem(AUTO_LEARN_KEY) !== '0')
  }, [])

  useEffect(() => {
    if (!selectedId && bots[0]) setSelectedId(bots[0].id)
  }, [bots, selectedId])

  const selected = bots.find((b) => b.id === selectedId) || bots[0] || null
  const adapt = (
    desk as Desk & {
      adapt?: {
        by_bot?: Record<string, Record<string, unknown>>
        rules?: Record<string, number>
        recent_vol?: unknown[]
      }
    }
  )?.adapt
  const adaptBot = selected ? adapt?.by_bot?.[selected.id] : undefined

  const learningTips = useMemo(() => {
    if (!selected) return [] as string[]
    return tipForBot(selected, adaptBot)
  }, [selected, adaptBot])

  const floorTips = useMemo(() => {
    const out: string[] = []
    if (desk?.paused_all) out.push('Desk paused_all is on — no tower should open new risk.')
    if (roi && roi.ok === false) out.push('ROI compliance not ok — check waivers/gaps before sizing up.')
    if (autoLearn) {
      out.push('Auto-learn ON: desk_adapt play-safe on high vol; size-up only on proven ≥80% records.')
    } else {
      out.push('Auto-learn tracking muted in this panel — adapt may still run on the paper desk.')
    }
    const rules = adapt?.rules
    if (rules?.big_needs_hit != null) {
      out.push(`Play-big needs hit ≥ ${rules.big_needs_hit} with n ≥ ${rules.big_needs_n ?? 12}.`)
    }
    return out
  }, [desk, roi, autoLearn, adapt])

  const allHistory = useMemo(() => {
    const rows = bots.flatMap(historyRows)
    rows.sort((a, b) => b.at - a.at || a.botName.localeCompare(b.botName))
    return rows
  }, [bots])

  const history = useMemo(() => {
    if (historyBot === 'all') return allHistory
    return allHistory.filter((row) => row.botId === historyBot)
  }, [allHistory, historyBot])

  const historyCap = historyLoad === 'all' ? history.length : Number(historyLoad)
  const historyShown = history.slice(0, historyCap)
  const historyNet = historyShown.reduce((sum, row) => sum + (row.pnl || 0), 0)
  const historyWins = historyShown.filter((row) => (row.pnl ?? 0) > 0).length
  const historyLosses = historyShown.filter((row) => (row.pnl ?? 0) < 0).length
  const historyName =
    historyBot === 'all' ? 'All towers' : bots.find((bot) => bot.id === historyBot)?.name || historyBot

  const floorBots = useMemo(() => {
    return bots.filter((bot) => {
      if (floorFilter === 'trading') return !isResearchTower(bot.id) && !isStaffSupport(bot.id)
      if (floorFilter === 'research') return isResearchTower(bot.id)
      if (floorFilter === 'support') return isStaffSupport(bot.id)
      if (floorFilter === 'open') return (bot.open_count ?? 0) > 0
      if (floorFilter === 'paused') return Boolean(bot.paused)
      return true
    })
  }, [bots, floorFilter])

  useEffect(() => {
    if (!floorBots.length) return
    if (!floorBots.some((bot) => bot.id === selectedId)) setSelectedId(floorBots[0].id)
  }, [floorBots, selectedId])

  const setNote = (id: string, text: string) => {
    const next = { ...notes, [id]: text }
    setNotes(next)
    saveNotes(next)
  }

  const toggleAutoLearn = () => {
    const next = !autoLearn
    setAutoLearn(next)
    localStorage.setItem(AUTO_LEARN_KEY, next ? '1' : '0')
  }

  const openHistory = (id: string) => {
    setHistoryBot(id)
    setSelectedId(id)
    setTab('history')
  }

  return (
    <div className="boss-dash" role="dialog" aria-label="Boss office dashboard">
      <div className="boss-dash-panel" onClick={(e) => e.stopPropagation()}>
        <header className="boss-dash-head">
          <div>
            <strong>BOSS OFFICE</strong>
            <span>Floor dashboard · paper desk · adapt learn</span>
          </div>
          <button type="button" className="back-btn" onClick={onClose}>
            Close board
          </button>
        </header>

        <div className="boss-tabs" role="tablist">
          {(
            [
              ['floor', 'Floor bots'],
              ['history', 'History'],
              ['learn', 'Learning'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              className={tab === id ? 'active' : ''}
              aria-selected={tab === id}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <p className="boss-pulse">
          <span>Today {money(desk?.today, true)}</span>
          <span>Realized {money(desk?.realized, true)}</span>
          <span>Open risk {money(desk?.open_risk)}</span>
          <span>Open {desk?.open_count ?? 0}</span>
          {desk?.trades_today != null && <span>Settles today {desk.trades_today}</span>}
          {desk?.next_check && <span>Next {desk.next_check}</span>}
          {desk?.paused_all && <span>Desk paused</span>}
          {desk?.ops?.entry_gate && <span>Gate {desk.ops.entry_gate}</span>}
        </p>

        {tab === 'floor' && (
          <div className="boss-grid">
            <div className="boss-table-wrap">
              <div className="boss-tools">
                <label>
                  Show
                  <select
                    aria-label="Floor filter"
                    value={floorFilter}
                    onChange={(e) => setFloorFilter(e.target.value as FloorFilter)}
                  >
                    <option value="all">All towers</option>
                    <option value="trading">Trading</option>
                    <option value="research">Research</option>
                    <option value="support">Support</option>
                    <option value="open">Open paper</option>
                    <option value="paused">Paused</option>
                  </select>
                </label>
                <span className="boss-muted">
                  {floorBots.length} of {bots.length}
                </span>
              </div>
              <table className="boss-table">
                <thead>
                  <tr>
                    <th>Bot</th>
                    <th>Status</th>
                    <th>Today</th>
                    <th>Realized</th>
                    <th>Cash</th>
                    <th>Open</th>
                    <th>Hit</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {floorBots.map((bot) => (
                    <tr
                      key={bot.id}
                      className={bot.id === selected?.id ? 'selected' : ''}
                      onClick={() => setSelectedId(bot.id)}
                    >
                      <td>{bot.name}</td>
                      <td>{statusLabel(bot)}</td>
                      <td>{money(bot.today, true)}</td>
                      <td>{money(bot.realized, true)}</td>
                      <td>{money(bot.cash)}</td>
                      <td>{bot.open_count ?? 0}</td>
                      <td>
                        {bot.expectancy_hit_rate == null
                          ? '—'
                          : `${Math.round(bot.expectancy_hit_rate * 100)}%`}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="boss-mini"
                          onClick={(e) => {
                            e.stopPropagation()
                            onFocusBot(bot.id)
                          }}
                        >
                          Open suite
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!floorBots.length && (
                    <tr>
                      <td colSpan={8}>No towers in this filter.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {selected && (
              <aside className="boss-side">
                <h3>{selected.name}</h3>
                <p className="boss-muted">
                  {selected.id}
                  {isStaffSupport(selected.id)
                    ? ' · support'
                    : isResearchTower(selected.id)
                      ? ' · research'
                      : ' · trading'}
                  {selected.paused ? ' · paused' : ''}
                  {' · '}
                  {selected.feed || 'feed'}
                </p>
                <p>
                  Realized {money(selected.realized, true)} · open risk {money(selected.open_risk)} ·
                  cash {money(selected.cash)}
                </p>
                {selected.next_run && <p>Next check {selected.next_run}</p>}
                {(selected.positions || []).length > 0 && (
                  <div className="boss-block">
                    <h4>Open paper</h4>
                    <ul className="boss-positions">
                      {(selected.positions || []).slice(0, 6).map((pos, i) => (
                        <li key={`${pos.ticker || pos.what || i}`}>
                          {String(pos.ticker || pos.what || pos.title || 'position')}
                          {pos.cost != null ? ` · ${money(pos.cost)}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="boss-block">
                  <h4>Buy / sell / failsafe</h4>
                  <p>{(selected.plans?.buy || []).join(' · ') || 'No buy plan on snapshot.'}</p>
                  <p>{(selected.plans?.sell || []).join(' · ') || 'No sell plan on snapshot.'}</p>
                  <p>
                    {(selected.plans?.failsafes || []).join(' · ') || 'No failsafe line on snapshot.'}
                  </p>
                </div>
                <button type="button" className="boss-mini" onClick={() => openHistory(selected.id)}>
                  This tower's history
                </button>
                <label className="boss-note">
                  Staff adjust note (local)
                  <textarea
                    value={notes[selected.id] || ''}
                    placeholder="e.g. tighten edge band after next settle…"
                    onChange={(e) => setNote(selected.id, e.target.value)}
                    rows={3}
                  />
                </label>
                <p className="boss-muted">
                  This board reads the paper snapshot and steers notes. It does not send orders or
                  invent fills. Deep ops: <a href="/pimp-trading">PIMP-TRADING</a>
                </p>
              </aside>
            )}
          </div>
        )}

        {tab === 'history' && (
          <div className="boss-history">
            <div className="boss-tools">
              <h3>{historyName} · recent settles</h3>
              <label>
                Tower
                <select
                  aria-label="History tower"
                  value={historyBot}
                  onChange={(e) => {
                    setHistoryBot(e.target.value)
                    if (e.target.value !== 'all') setSelectedId(e.target.value)
                  }}
                >
                  <option value="all">All towers</option>
                  {bots.map((bot) => (
                    <option key={bot.id} value={bot.id}>
                      {bot.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Loaded
                <select
                  aria-label="Trades loaded"
                  value={historyLoad}
                  onChange={(e) => setHistoryLoad(e.target.value as HistoryLoad)}
                >
                  <option value="60">60</option>
                  <option value="100">100</option>
                  <option value="200">200</option>
                  <option value="all">All</option>
                </select>
              </label>
            </div>
            {!history.length ? (
              <p className="boss-muted">No closed paper settles for this filter.</p>
            ) : (
              <ul>
                {historyShown.map((row) => (
                  <li key={row.key} className={historyBot === 'all' ? 'all' : ''}>
                    <span>{row.when}</span>
                    {historyBot === 'all' && <span>{row.botName}</span>}
                    <span>
                      {row.what}
                      {row.result ? <em className="boss-result"> {row.result}</em> : null}
                    </span>
                    <span className={(row.pnl ?? 0) >= 0 ? 'up' : 'down'}>{money(row.pnl, true)}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="boss-muted">
              Loaded {historyShown.length} of {history.length} · net {money(historyNet, true)} ·{' '}
              {historyWins} won · {historyLosses} lost
              {' · '}
              Desk today {money(desk?.today, true)} · open risk {money(desk?.open_risk)} ·{' '}
              {desk?.status_line || snap?.banner || 'paper desk'}
            </p>
          </div>
        )}

        {tab === 'learn' && (
          <div className="boss-learn">
            <div className="boss-learn-head">
              <label className="boss-toggle">
                <input type="checkbox" checked={autoLearn} onChange={toggleAutoLearn} />
                Auto-learn tracking (desk_adapt)
              </label>
              <label>
                Tower
                <select
                  aria-label="Learning tower"
                  value={selected?.id || ''}
                  onChange={(e) => setSelectedId(e.target.value)}
                >
                  {bots.map((bot) => (
                    <option key={bot.id} value={bot.id}>
                      {bot.name}
                    </option>
                  ))}
                </select>
              </label>
              <span className="boss-muted">Vol play-safe · size-up on proven ≥80% · paper only</span>
            </div>
            <div className="boss-learn-cols">
              <section>
                <h4>Floor tips</h4>
                <ul>
                  {floorTips.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </section>
              <section>
                <h4>{selected ? `${selected.name} tips` : 'Bot tips'}</h4>
                <ul>
                  {learningTips.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
                {selected && (
                  <button
                    type="button"
                    className="boss-mini"
                    onClick={() => {
                      const next = bots[(bots.findIndex((b) => b.id === selected.id) + 1) % bots.length]
                      if (next) setSelectedId(next.id)
                    }}
                  >
                    Next bot tips
                  </button>
                )}
              </section>
              <section>
                <h4>Adapt pulse</h4>
                <ul>
                  {Object.keys(adapt?.by_bot || {}).length === 0 && (
                    <li>No adapt_state rows in snapshot yet — desk still runs play-safe defaults.</li>
                  )}
                  {Object.entries(adapt?.by_bot || {}).map(([id, row]) => (
                    <li key={id}>{adaptLine(id, row, bots.find((bot) => bot.id === id)?.name || id)}</li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
