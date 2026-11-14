import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  beamColorFor,
  bookCash,
  towerBookCash,
  towerClosed,
  towerInCity,
  hologramPnl,
  hologramPnlValue,
  money,
  pnlTone,
  statusLabel,
} from '../data/format'
import { isResearchTower, isStaffSupport, isSupportTower } from '../data/floorMap'
import type { BotRow, Desk } from '../types'
import { marketSession, untilOpen, useMarketNow } from '../data/marketHours'
import {
  districtSign,
  hiddenLot,
  nextCheckIn,
  resultsProgress,
  searchTowers,
  timerLabel,
  tradesCsv,
  whyNoTrade,
} from '../data/cityRules'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelect: (id: string) => void
  /** Browser time (ms) the snapshot was read. Card countdowns run from here. */
  readAt?: number | null
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

/** Market-closed rows sink to the bottom; the rest keep their desk order. */
function byOpenFirst(bots: BotRow[], now: Date) {
  return bots
    .map((bot, i) => ({ bot, i, shut: Boolean(marketSession(bot.id, now) && !marketSession(bot.id, now)?.open) }))
    .sort((a, b) => Number(a.shut) - Number(b.shut) || a.i - b.i)
    .map((r) => r.bot)
}

function TowerGroup({
  label,
  bots,
  all,
  desk,
  onSelect,
  now,
  liveTrades,
  subgroups,
  readAt,
  expanded = false,
  cardsOpen = false,
}: {
  readAt?: number | null
  /** Full-screen page: the list lays out as a grid. */
  expanded?: boolean
  /** Cards start open. */
  cardsOpen?: boolean
  label: string
  bots: BotRow[]
  all: BotRow[]
  desk?: Desk
  onSelect: (id: string) => void
  now: Date
  /** Open paper positions across this group. Shown beside the heading. */
  liveTrades?: number
  subgroups?: { label: string; bots: BotRow[] }[]
}) {
  if (!bots.length) return null
  const parts = subgroups?.filter((g) => g.bots.length) || [{ label: '', bots }]
  return (
    <section className="tower-menu-group" aria-label={label}>
      <h3 className="tower-menu-heading">
        <span>{label}</span>
        {liveTrades != null && <span className="tower-tab-open tower-menu-live">Live Trades: {liveTrades}</span>}
      </h3>
      {parts.map((part) => (
        <div key={part.label || label}>
          {part.label && <h4 className="tower-menu-subheading">{part.label}</h4>}
          <ul className={expanded ? 'tower-menu-list tower-page-grid' : 'tower-menu-list'}>
            {byOpenFirst(part.bots, now).map((bot) => (
              <TowerTab
                key={bot.id}
                bot={bot}
                desk={desk}
                index={Math.max(0, all.indexOf(bot))}
                onSelect={onSelect}
                now={now}
                readAt={readAt}
                expanded={expanded}
                cardsOpen={cardsOpen}
              />
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

function TowerTab({
  bot,
  desk,
  index,
  onSelect,
  now,
  readAt,
  expanded = false,
  cardsOpen = false,
}: {
  bot: BotRow
  desk?: Desk
  index: number
  onSelect: (id: string) => void
  now: Date
  readAt?: number | null
  expanded?: boolean
  cardsOpen?: boolean
}) {
  const color = beamColorFor(bot.id, index)
  const closed = towerClosed(bot)
  const session = marketSession(bot.id, now)
  const shut = Boolean(session && !session.open)
  const countdown = untilOpen(session, now)
  const status = statusLabel(bot)
  const staff = isStaffSupport(bot.id)
  const supportIdle = (isResearchTower(bot.id) || staff) && !closed && !bookPnlApplies(bot)
  const cash = towerBookCash(desk, bot)
  const tone = closed || supportIdle ? 'flat' : pnlTone(hologramPnlValue(bot))
  const desks = bot.traders && bot.traders >= 100 ? bot.traders : 120
  const figure = closed
    ? bot.present === false
      ? 'offline'
      : 'paused'
    : staff
      ? `6 desks · ${desks}`
      : supportIdle
        ? supportHeadline(bot)
        : hologramPnl(bot)
  const card = bot.card
  const skipFlag = Boolean(card?.learning_skip)
  const errorLight = Boolean(card?.error)
  return (
    <li className={expanded ? 'tower-page-item' : undefined}>
      <button
        type="button"
        aria-label={`${bot.name}. ${closed ? 'Closed.' : ''} ${figure}. Open tower.`}
        className={`tower-tab ${closed ? 'closed' : ''} ${shut ? 'market-shut' : ''}`}
        style={{ ['--tab-beam' as string]: closed || shut ? '#3a4152' : color }}
        onClick={() => onSelect(bot.id)}
        title={status}
      >
        <span className="tower-tab-beam" aria-hidden />
        <span className="tower-tab-body">
          <span className="tower-tab-name">
            {bot.name}
            {skipFlag && (
              <span className="tower-flag skip" title={card?.learning_skip} aria-label="Paused by a learning skip">
                skip
              </span>
            )}
            {errorLight && (
              <span className="tower-flag error" title={card?.error} aria-label={`Error: ${card?.error}`} />
            )}
            {shut && (
              <span className="tower-tab-shut">
                <span className="tower-tab-shut-word">Closed</span>
                {countdown && (
                  <span className="tower-tab-open" title={`Time until the ${session?.label} opens`}>
                    opens in {countdown}
                  </span>
                )}
              </span>
            )}
          </span>
          <span className="tower-tab-meta">
            <span className={supportIdle ? 'tower-tab-pnl tower-tab-wait' : `tower-tab-pnl tone-${tone}`}>
              {figure}
            </span>
            {!supportIdle && !closed && bot.open_count != null && bot.open_count > 0 && (
              <span className="tower-tab-open">open {bot.open_count}</span>
            )}
            {cash != null && <span className="tower-tab-cash">{money(cash)}</span>}
            {!towerInCity(bot) && <span className="tower-tab-offcity">not in city until it trades</span>}
          </span>
          {!supportIdle && <span className="tower-tab-status">{status}</span>}
          {staff && !closed && <span className="tower-tab-status">One book. It does not trade.</span>}
        </span>
      </button>
      <TowerCard bot={bot} now={now} readAt={readAt} startOpen={cardsOpen} />
    </li>
  )
}

function downloadCsv(bot: BotRow) {
  const blob = new Blob([tradesCsv(bot)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${bot.id}-paper-trades.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Plain-words card: what it trades, how often, today's result, why no trade. */
function TowerCard({
  bot,
  now,
  readAt,
  startOpen = false,
}: {
  bot: BotRow
  now: Date
  readAt?: number | null
  startOpen?: boolean
}) {
  const card = bot.card
  const t = card?.today
  const timer = timerLabel(bot)
  const elapsed = readAt ? (now.getTime() - readAt) / 1000 : 0
  const next = nextCheckIn(bot, elapsed)
  const why = whyNoTrade(bot)
  const progress = resultsProgress(bot)
  const floor = card?.floor ?? bot.venue_min_edge
  const history = [...(bot.history || [])].slice(-12).reverse()
  const open = bot.positions || []
  return (
    <details className="tower-card" open={startOpen || undefined}>
      <summary aria-label={`Card for ${bot.name}`}>card</summary>
      <div className="tower-card-body">
        <p className="tower-card-sign">{districtSign(bot)}</p>
        {bot.blurb && <p>{bot.blurb}</p>}
        {(timer || next) && (
          <p>
            {timer && <span>Checks {timer}.</span>} {next && <span>{next[0].toUpperCase() + next.slice(1)}.</span>}
          </p>
        )}
        {(bot.card?.scan_times?.length || 0) > 0 && timer.startsWith('every') && (
          <p>Scan times: {bot.card?.scan_times?.join(', ')} CT.</p>
        )}
        <p>
          Today: {t?.settled || 0} settled, {t?.wins || 0} won, {t?.losses || 0} lost
          {t?.pnl != null ? `, ${money(t.pnl, true)}` : ''}. Fees paid today {money(t?.fees || 0)}.
        </p>
        {(t?.early_sales || t?.held) ? (
          <p>
            Sold early {t?.early_sales || 0} ({money(t?.early_pnl || 0, true)}) · held to the result{' '}
            {t?.held || 0} ({money(t?.held_pnl || 0, true)}).
          </p>
        ) : null}
        {(t?.best || t?.worst) && (
          <p>
            {t?.best && <span>Best today: {t.best.what} {money(t.best.pnl, true)}. </span>}
            {t?.worst && <span>Worst today: {t.worst.what} {money(t.worst.pnl, true)}.</span>}
          </p>
        )}
        {bot.lifetime?.realized != null && (
          <p>
            Lifetime {money(bot.lifetime.realized, true)} ({bot.lifetime.wins || 0} won, {bot.lifetime.losses || 0}{' '}
            lost). Losses included.
          </p>
        )}
        {why && (
          <p className="tower-card-why">
            {(t?.settled || 0) > 0 ? 'Last check: ' : 'Why no trade: '}
            {why}
          </p>
        )}
        {card?.learning_skip && <p className="tower-card-skip">Learning skip: {card.learning_skip}</p>}
        {card?.error && <p className="tower-card-error">Error: {card.error}</p>}
        {floor != null && <p>Edge floor {Number(floor).toFixed(2)} (locked, never lower).</p>}
        {progress && (
          <div className="tower-card-progress" role="progressbar" aria-valuemin={0} aria-valuemax={progress.need} aria-valuenow={Math.min(progress.have, progress.need)} aria-label="Results toward 50">
            <span style={{ width: `${progress.pct}%` }} />
            <em>{progress.note}</em>
          </div>
        )}
        {(history.length > 0 || open.length > 0) && (
          <details className="tower-card-trades">
            <summary>trades ({open.length} open, {(bot.history || []).length} settled)</summary>
            <ul>
              {open.map((p, i) => (
                <li key={`o${i}`}>
                  open · {String(p.what || p.title || p.team || p.ticker || 'position')}
                  {p.cost != null ? ` · ${money(p.cost)}` : ''}
                </li>
              ))}
              {history.map((h, i) => (
                <li key={`h${i}`} className={`tone-${pnlTone(h.pnl)}`}>
                  {String(h.closed_at || h.when || '')} · {String(h.what || h.title || h.team || 'trade')} ·{' '}
                  {money(h.pnl, true)} {h.exit_reason ? `· ${h.exit_reason}` : ''}
                </li>
              ))}
            </ul>
          </details>
        )}
        <button type="button" className="tower-card-csv" onClick={() => downloadCsv(bot)}>
          Export trades (CSV)
        </button>
      </div>
    </details>
  )
}


/** Trading (desk and practice), Research, Support and the hidden lot. Shared by the list and the full page. */
function TowerSections({
  bots,
  lot,
  desk,
  query,
  now,
  readAt,
  onSelect,
  expanded = false,
  cardsOpen = false,
}: {
  bots: BotRow[]
  lot: BotRow[]
  desk?: Desk
  query: string
  now: Date
  readAt?: number | null
  onSelect: (id: string) => void
  expanded?: boolean
  cardsOpen?: boolean
}) {
  const research = bots.filter((bot) => isSupportTower(bot.id))
  const support = bots.filter((bot) => isStaffSupport(bot.id))
  const trading = bots.filter((bot) => !isResearchTower(bot.id) && !isStaffSupport(bot.id))
  const deskBots = trading.filter((bot) => !bot.shadow_only)
  const practiceBots = trading.filter((bot) => bot.shadow_only)
  const liveTrades = trading.reduce((n, bot) => n + Math.max(0, Number(bot.open_count) || 0), 0)
  return (
    <>
      <TowerGroup
        label="Trading"
        bots={trading}
        all={bots}
        desk={desk}
        now={now}
        readAt={readAt}
        liveTrades={liveTrades}
        expanded={expanded}
        cardsOpen={cardsOpen}
        subgroups={[
          { label: 'Desk · spends vault cash', bots: deskBots },
          { label: 'Practice · own book', bots: practiceBots },
        ]}
        onSelect={onSelect}
      />
      <TowerGroup label="Research" bots={research} all={bots} desk={desk} now={now} readAt={readAt} expanded={expanded} cardsOpen={cardsOpen} onSelect={onSelect} />
      <TowerGroup label="Support" bots={support} all={bots} desk={desk} now={now} readAt={readAt} expanded={expanded} cardsOpen={cardsOpen} onSelect={onSelect} />
      {!query && lot.length > 0 && (
        <details className="tower-menu-group tower-lot">
          <summary className="tower-menu-heading">
            <span>Hidden lot</span>
            <span className="tower-menu-live">{lot.length} waiting to trade</span>
          </summary>
          <ul className="tower-menu-list">
            {lot.map((bot) => {
              const cash = towerBookCash(desk, bot)
              return (
                <li key={bot.id} className="tower-lot-row">
                  {bot.name}
                  {cash != null ? ` · ${money(cash)}` : ''} · not in the city until it trades
                </li>
              )
            })}
          </ul>
        </details>
      )}
    </>
  )
}

/** Hash that opens the full-screen tower page, so the browser Back button closes it. */
export const TOWER_PAGE_HASH = '#towers'

/**
 * Full-screen tower page: every tower in the same groups as the list, cards open,
 * laid out in columns. Esc, the Close button or Back returns to the city.
 */
function TowerPage({
  allBots,
  desk,
  now,
  readAt,
  onSelect,
  onClose,
}: {
  allBots: BotRow[]
  desk?: Desk
  now: Date
  readAt?: number | null
  onSelect: (id: string) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [allOpen, setAllOpen] = useState(true)
  const closeRef = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])
  const lot = hiddenLot(allBots)
  const lotIds = new Set(lot.map((b) => b.id))
  const bots = searchTowers(query ? allBots : allBots.filter((b) => !lotIds.has(b.id)), query)
  const live = bots.filter((b) => !towerClosed(b) && !(marketSession(b.id, now) && !marketSession(b.id, now)?.open)).length
  return createPortal(
    <div className="tower-page" role="dialog" aria-modal="true" aria-label="All towers">
      <header className="tower-page-head">
        <div className="tower-page-title">
          <strong>Towers</strong>
          <em>
            {live}/{bots.length} live · paper cash {money(bookCash(desk, allBots))}
          </em>
        </div>
        <label className="tower-search tower-page-search">
          <span className="sr-only">Find a tower by name</span>
          <input
            type="search"
            placeholder="Find a tower"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Find a tower by name"
          />
        </label>
        <button type="button" className="tower-page-btn" onClick={() => setAllOpen((v) => !v)}>
          {allOpen ? 'Fold cards' : 'Open cards'}
        </button>
        <button type="button" className="tower-page-btn tower-page-close" ref={closeRef} onClick={onClose}>
          Close ✕
        </button>
      </header>
      <div className="tower-page-body" key={allOpen ? 'open' : 'folded'}>
        <TowerSections
          bots={bots}
          lot={lot}
          desk={desk}
          query={query}
          now={now}
          readAt={readAt}
          expanded
          cardsOpen={allOpen}
          onSelect={(id) => {
            onClose()
            onSelect(id)
          }}
        />
        {query && !bots.length && <p className="tower-search-none">No tower matches that name.</p>}
      </div>
    </div>,
    document.body,
  )
}

/**
 * Compact tower dropdown — keeps the plaza clear.
 * World holograms stay as quiet name tags; this menu is the accessible hit target.
 */
export function TowerRail({ bots: allBots, desk, onSelect, readAt }: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(() => typeof window !== 'undefined' && window.location.hash === TOWER_PAGE_HASH)
  const now = useMarketNow()
  const rootRef = useRef<HTMLDivElement | null>(null)
  const pushedRef = useRef(false)
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

  useEffect(() => {
    const onHash = () => setPage(window.location.hash === TOWER_PAGE_HASH)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const openPage = () => {
    setOpen(false)
    if (window.location.hash !== TOWER_PAGE_HASH) {
      pushedRef.current = true
      window.location.hash = TOWER_PAGE_HASH
    }
    setPage(true)
  }
  const closePage = () => {
    setPage(false)
    if (window.location.hash !== TOWER_PAGE_HASH) return
    if (pushedRef.current) {
      pushedRef.current = false
      history.back()
    } else {
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }

  if (!allBots.length) return null

  // Hidden lot: practice towers that have not traded yet. They stay off the
  // plaza and fold into one closed row here until they wake.
  const lot = hiddenLot(allBots)
  const lotIds = new Set(lot.map((b) => b.id))
  const bots = searchTowers(
    query ? allBots : allBots.filter((b) => !lotIds.has(b.id)),
    query,
  )

  const live = bots.filter((b) => !towerClosed(b) && !(marketSession(b.id, now) && !marketSession(b.id, now)?.open)).length
  const paperCash = bookCash(desk, allBots)
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
              style={{
                background:
                  towerClosed(bot) || (marketSession(bot.id, now) && !marketSession(bot.id, now)?.open)
                    ? '#3a4152'
                    : beamColorFor(bot.id, i),
              }}
            />
          ))}
        </span>
        <span className="tower-menu-copy">
          <strong>Towers</strong>
          <em>
            {live}/{bots.length} live
            {paperCash != null ? ` · paper cash ${money(paperCash)}` : ''}
          </em>
        </span>
        <span className="tower-menu-caret" aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>

      {open && (
        <nav className="tower-menu-panel" aria-label="Paper towers" id={listId}>
          <button type="button" className="tower-menu-full" onClick={openPage} title="Open every tower on one page">
            ⛶ Full screen
          </button>
          <label className="tower-search">
            <span className="sr-only">Find a tower by name</span>
            <input
              type="search"
              placeholder="Find a tower"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Find a tower by name"
            />
          </label>
          <TowerSections
            bots={bots}
            lot={lot}
            desk={desk}
            query={query}
            now={now}
            readAt={readAt}
            onSelect={(id) => {
              setOpen(false)
              onSelect(id)
            }}
          />
          {query && !bots.length && <p className="tower-search-none">No tower matches that name.</p>}
        </nav>
      )}
      {page && (
        <TowerPage allBots={allBots} desk={desk} now={now} readAt={readAt} onSelect={onSelect} onClose={closePage} />
      )}
    </div>
  )
}
