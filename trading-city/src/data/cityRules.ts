/**
 * City page rules (plan steps 806-885). Pure helpers, no React and no three.js,
 * so the look rules can be tested in plain Node (tests/city_rules.test.mjs).
 *
 * Levi's look rules:
 *   - towers, not television (no screens or video walls on a tower)
 *   - closed or paused towers are black with blacked-out windows
 *   - practice (shadow) towers stay hidden until they trade
 * Honest numbers: losses always count in every total shown here.
 */
import type { BotRow, CityBannerFacts, Desk, TradeOrHistory } from '../types'
import { towerClosed, towerInCity } from './format'

/** Blacked-out window color for a closed or paused tower. */
export const BLACKED_OUT = '#030306'
/** Shell color for a closed or paused tower. */
export const CLOSED_SHELL = '#000000'
export const ROOF_UP = '#39ff14'
export const ROOF_DOWN = '#ff2a6d'
export const ROOF_FLAT = '#7a8194'
/** Data older than this gets a gray "stale" stamp. */
export const STALE_AFTER_SEC = 300
/** Practice towers count after this many settled results. */
export const RESULTS_NEEDED = 50

export type Tone = 'up' | 'down' | 'flat'

function num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** Today's result for a tower. Settled results first, else the desk's today figure. */
export function todayPnl(bot: BotRow): number {
  const fromCard = num(bot.card?.today?.pnl)
  const fromBot = num(bot.today)
  if (fromBot != null && fromBot !== 0) return fromBot
  return fromCard ?? fromBot ?? 0
}

export function toneOf(n: number | null | undefined): Tone {
  if (n == null || Math.abs(n) < 0.005) return 'flat'
  return n > 0 ? 'up' : 'down'
}

/** Roof color by today's result: green up, red down, gray flat. Closed towers stay black. */
export function roofColor(bot: BotRow, closed = towerClosed(bot)): string {
  if (closed) return CLOSED_SHELL
  const tone = toneOf(todayPnl(bot))
  return tone === 'up' ? ROOF_UP : tone === 'down' ? ROOF_DOWN : ROOF_FLAT
}

/** Trades today: settled today plus still open. */
export function tradesToday(bot: BotRow): number {
  const fromCard = num(bot.card?.trades_today)
  if (fromCard != null) return Math.max(0, fromCard)
  return Math.max(0, num(bot.open_count) || 0)
}

/**
 * Share of a tower's windows that are lit, by today's trade count.
 * Closed towers: 0 (blacked out). A quiet open tower keeps a few lights on.
 */
export function windowLitShare(bot: BotRow, closed = towerClosed(bot)): number {
  if (closed) return 0
  const n = tradesToday(bot)
  return Math.min(1, 0.22 + n * 0.1)
}

/**
 * Tower height follows lifetime results (losses included), capped so no tower
 * dwarfs the city. Base keeps the old skyline rhythm.
 */
export function towerHeight(bot: BotRow, index: number, offline = bot.present === false): number {
  if (offline) return 5.4
  const base = 7.6 + (index % 3) * 1.35 + (index === 0 ? 1.2 : 0)
  const life = num(bot.lifetime?.realized) ?? num(bot.realized) ?? 0
  const extra = Math.max(-1.5, Math.min(3, life / 250))
  return Math.round((base + extra) * 100) / 100
}

/** "every 60s", "every 5 min", "scans at 12:05, 13:05 CT". */
export function timerLabel(bot: BotRow): string {
  const every = num(bot.card?.every_sec)
  if (every && every > 0) {
    if (every < 120) return `every ${every}s`
    if (every % 60 === 0) return `every ${every / 60} min`
    return `every ${every}s`
  }
  const scans = bot.card?.scan_times || []
  if (scans.length) return `scans at ${scans.join(', ')} CT`
  return ''
}

export function shortDuration(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return ''
  const s = Math.max(0, Math.round(sec))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = s % 60
  if (m < 60) return r ? `${m}m ${String(r).padStart(2, '0')}s` : `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h ${String(m % 60).padStart(2, '0')}m`
}

/** "next check in 42s". Counts down from the snapshot read time. */
export function nextCheckIn(bot: BotRow, elapsedSec = 0): string {
  const raw = num(bot.card?.next_check_in_sec)
  if (raw == null) return ''
  const left = raw - Math.max(0, elapsedSec)
  if (left <= 0) return 'next check due now'
  return `next check in ${shortDuration(left)}`
}

/** Why the tower did not buy, in plain words. Empty while it holds a trade. */
export function whyNoTrade(bot: BotRow): string {
  const fromCard = bot.card?.why_no_trade
  if (typeof fromCard === 'string') return fromCard
  if ((num(bot.open_count) || 0) > 0) return ''
  const bits = [bot.why, bot.skip, bot.idle_copy, bot.feed].filter(
    (s) => typeof s === 'string' && s.trim(),
  ) as string[]
  return bits[0] || ''
}

/** 50-results bar for practice towers. Null for desk and research towers. */
export function resultsProgress(bot: BotRow): { have: number; need: number; pct: number; note: string } | null {
  const p = bot.card?.progress
  if (!p) return null
  const need = num(p.need) || RESULTS_NEEDED
  const have = Math.max(0, num(p.have) || 0)
  return { have, need, pct: Math.min(100, Math.round((have / need) * 100)), note: p.note || `${have} of ${need} results` }
}

/** Data age in whole seconds. Prefers the server read time, else the browser fetch time. */
export function dataAgeSec(snapCachedAt: number | null | undefined, updatedAt: number | null | undefined, nowMs: number): number | null {
  const server = num(snapCachedAt)
  if (server != null && server > 0) return Math.max(0, Math.round(nowMs / 1000 - server))
  const local = num(updatedAt)
  if (local != null && local > 0) return Math.max(0, Math.round((nowMs - local) / 1000))
  return null
}

export function isStale(ageSec: number | null): boolean {
  return ageSec != null && ageSec > STALE_AFTER_SEC
}

const CT_PARTS = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago',
  hour: 'numeric',
  minute: '2-digit',
  hour12: false,
  weekday: 'short',
})

function ctHourMinute(now: Date): { h: number; m: number; wd: string } {
  const parts = CT_PARTS.formatToParts(now)
  const get = (t: string) => parts.find((p) => p.type === t)?.value || ''
  return { h: Number(get('hour')) % 24, m: Number(get('minute')), wd: get('weekday') }
}

/** Quiet hours: 10 PM to 7 AM Central. The city dims. */
export function isQuietHours(now: Date): boolean {
  const { h } = ctHourMinute(now)
  return h >= 22 || h < 7
}

/** "3:05 PM CT". */
export function centralClock(now: Date): string {
  return (
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Chicago',
      hour: 'numeric',
      minute: '2-digit',
    }).format(now) + ' CT'
  )
}

/** Stock market hours line for the city clock (8:30 AM to 3 PM CT, weekdays). */
export function stockHoursLine(now: Date): string {
  const { h, m, wd } = ctHourMinute(now)
  const weekend = wd === 'Sat' || wd === 'Sun'
  const mins = h * 60 + m
  if (!weekend && mins >= 8 * 60 + 30 && mins < 15 * 60) return 'stocks open'
  return 'stocks closed'
}

/** Find towers by name or id. Empty search keeps every tower. */
export function searchTowers(bots: BotRow[], query: string): BotRow[] {
  const q = query.trim().toLowerCase()
  if (!q) return bots
  return bots.filter((b) => `${b.name || ''} ${b.id || ''}`.toLowerCase().includes(q))
}

/** Practice towers not standing yet: the hidden lot until they wake. */
export function hiddenLot(bots: BotRow[]): BotRow[] {
  return bots.filter((b) => !towerInCity(b))
}

const DISTRICT_SIGNS: Record<string, string> = {
  vault: 'Vault district',
  sports: 'Sports district',
  crypto: 'Crypto district',
  markets: 'Markets district',
  weather: 'Weather district',
  research: 'Research district',
}

export function districtSign(bot: BotRow): string {
  const d = bot.card?.district || (bot.shadow_only ? 'markets' : 'vault')
  return DISTRICT_SIGNS[d] || 'Markets district'
}

function csvCell(v: unknown): string {
  if (v == null) return ''
  const s = String(v)
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** One tower's trades as CSV: settled rows (wins and losses) then open rows. */
export function tradesCsv(bot: BotRow): string {
  const head = ['tower', 'state', 'when', 'what', 'side', 'cost', 'fee', 'pnl', 'result', 'exit']
  const rows: string[][] = [head]
  const add = (state: string, t: TradeOrHistory) => {
    rows.push(
      [
        bot.name,
        state,
        t.closed_at || t.when || t.closed || '',
        t.what || t.title || t.team || t.ticker || t.game || '',
        (t.side as string) || '',
        t.cost as string,
        t.fee as string,
        t.pnl == null ? '' : String(t.pnl),
        t.result || '',
        t.exit_reason || t.exit || '',
      ].map(csvCell),
    )
  }
  for (const t of bot.history || []) add('settled', t)
  for (const t of (bot.positions || []) as TradeOrHistory[]) add('open', t)
  return rows.map((r) => r.join(',')).join('\n') + '\n'
}

/** Banner numbers. Uses the desk's city row, else works them out from the desk and limits. */
export function bannerFacts(desk: Desk | undefined, limits: Record<string, unknown> | undefined): CityBannerFacts {
  const c = desk?.city
  if (c && !c.error) return c
  const today = num(desk?.today) || 0
  const stop = num(limits?.daily_loss_stop) || 150
  const gate = String(desk?.gate || '')
  const halted = Boolean(desk?.paused_all) || /daily loss stop is hit/i.test(gate)
  return {
    real_money: 'off',
    today,
    lifetime_realized: num(desk?.lifetime?.realized),
    lifetime_wins: num(desk?.lifetime?.wins) || 0,
    lifetime_losses: num(desk?.lifetime?.losses) || 0,
    stop,
    stop_left: Math.max(0, stop + Math.min(0, today)),
    open_count: num(desk?.open_count) || 0,
    max_open: num(limits?.max_open_positions) || 12,
    open_risk: num(desk?.open_risk) || 0,
    max_open_risk: num(limits?.max_open_risk) || 100,
    halted,
    halt_reason: halted ? gate : '',
    gate,
  }
}

/** Plain-words legend for the colors and lights. */
export const LEGEND: { swatch: string; words: string }[] = [
  { swatch: ROOF_UP, words: 'Green roof: the tower is up today.' },
  { swatch: ROOF_DOWN, words: 'Red roof: the tower is down today.' },
  { swatch: ROOF_FLAT, words: 'Gray roof: flat today, no result yet.' },
  { swatch: '#f4f0d4', words: 'More lit windows: more trades today.' },
  { swatch: CLOSED_SHELL, words: 'Black tower, dark windows: closed or paused.' },
  { swatch: '#f9c80e', words: 'Yellow flag: paused by a learning skip.' },
  { swatch: '#ff5c5c', words: 'Red light: the last check had an error. It clears after a clean check.' },
  { swatch: '#3a4152', words: 'Practice towers stay hidden until they trade.' },
]
