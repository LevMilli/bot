import { useEffect, useMemo, useState } from 'react'
import type { BotRow, Desk, RoiSystem, Snapshot } from '../types'
import { money, statusLabel } from '../data/format'

const NOTES_KEY = 'apex-city-boss-notes-v1'
const AUTO_LEARN_KEY = 'apex-city-auto-learn-v1'

type StaffNotes = Record<string, string>

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
  const [tab, setTab] = useState<'floor' | 'history' | 'learn'>('floor')

  useEffect(() => {
    setNotes(loadNotes())
    setAutoLearn(localStorage.getItem(AUTO_LEARN_KEY) !== '0')
  }, [])

  useEffect(() => {
    if (!selectedId && bots[0]) setSelectedId(bots[0].id)
  }, [bots, selectedId])

  const selected = bots.find((b) => b.id === selectedId) || bots[0] || null
  const adapt = (desk as Desk & { adapt?: { by_bot?: Record<string, Record<string, unknown>>; rules?: Record<string, number>; recent_vol?: unknown[] } })
    ?.adapt
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

  const history = selected?.history?.slice(-12).reverse() || selected?.trades?.slice(-12).reverse() || []

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

        {tab === 'floor' && (
          <div className="boss-grid">
            <div className="boss-table-wrap">
              <table className="boss-table">
                <thead>
                  <tr>
                    <th>Bot</th>
                    <th>Status</th>
                    <th>Today</th>
                    <th>Cash</th>
                    <th>Open</th>
                    <th>Hit</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {bots.map((bot) => (
                    <tr
                      key={bot.id}
                      className={bot.id === selected?.id ? 'selected' : ''}
                      onClick={() => setSelectedId(bot.id)}
                    >
                      <td>{bot.name}</td>
                      <td>{statusLabel(bot)}</td>
                      <td>{money(bot.today, true)}</td>
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
                </tbody>
              </table>
            </div>
            {selected && (
              <aside className="boss-side">
                <h3>{selected.name}</h3>
                <p className="boss-muted">{selected.id} · {selected.feed || 'feed'}</p>
                <div className="boss-block">
                  <h4>Buy / sell / failsafe</h4>
                  <p>
                    {(selected.plans?.buy || []).join(' · ') || 'No buy plan on snapshot.'}
                  </p>
                  <p>
                    {(selected.plans?.sell || []).join(' · ') || 'No sell plan on snapshot.'}
                  </p>
                  <p>
                    {(selected.plans?.failsafes || []).join(' · ') ||
                      'No failsafe line on snapshot.'}
                  </p>
                </div>
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
                  Live stake edits run through the paper desk / adapt layer — this board tracks and
                  steers; it does not invent fills. Deep ops:{' '}
                  <a href="/pimp-trading">PIMP-TRADING</a>
                </p>
              </aside>
            )}
          </div>
        )}

        {tab === 'history' && selected && (
          <div className="boss-history">
            <h3>
              {selected.name} · recent settles
            </h3>
            {!history.length ? (
              <p className="boss-muted">No closed paper history on snapshot yet.</p>
            ) : (
              <ul>
                {history.map((row, i) => (
                  <li key={`${String(row.when || row.closed || row.closed_at || i)}-${i}`}>
                    <span>{String(row.when || row.closed || row.closed_at || '—')}</span>
                    <span>{String(row.ticker || row.what || row.title || 'trade')}</span>
                    <span className={Number(row.pnl) >= 0 ? 'up' : 'down'}>
                      {money(row.pnl, true)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="boss-muted">
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
              <span className="boss-muted">
                Vol play-safe · size-up on proven ≥80% · paper only
              </span>
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
                  {Object.entries(adapt?.by_bot || {})
                    .slice(0, 8)
                    .map(([id, row]) => (
                      <li key={id}>
                        <strong>{id}</strong> · {JSON.stringify(row).slice(0, 120)}
                      </li>
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
