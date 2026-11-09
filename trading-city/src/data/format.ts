import type { BotRow, Money, TradeOrHistory } from '../types'

/**
 * Unique neon beam per tower / teller. Index fallback must stay longer than the
 * BOTS roster so Sports gap and Sized Kalshi never share cyan again.
 */
export const BEAM_COLORS = [
  '#2de2e6', // cyan
  '#ff2a6d', // magenta
  '#39ff14', // lime
  '#f9c80e', // amber
  '#b967ff', // violet
  '#ff8c42', // coral — 6th tower (Sized Kalshi)
  '#4d9fff', // sky
  '#ff4d9a', // hot pink
] as const

/** Stable id → color so reordering bots does not reshuffle building colors. */
export const BOT_BEAM_COLORS: Record<string, string> = {
  'sports-gap': '#2de2e6',
  'kalshi-sp': '#ff2a6d',
  btc15m: '#39ff14',
  'commodity-15m': '#f9c80e',
  memecoin: '#b967ff',
  'kalshi-sized': '#ff8c42',
  'coinbase-spot': '#4d9fff',
  'btc-carry': '#ff4d9a',
}

function hashBotId(id: string): number {
  let h = 2166136261
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/**
 * Color for a tower / vault teller station.
 * Known bots use the map; new buildings get a deterministic free palette color.
 */
export function beamColorFor(botId: string | null | undefined, index = 0): string {
  if (botId && BOT_BEAM_COLORS[botId]) return BOT_BEAM_COLORS[botId]
  if (botId) {
    const known = new Set(Object.values(BOT_BEAM_COLORS))
    const free = BEAM_COLORS.filter((c) => !known.has(c))
    const pool = free.length ? free : [...BEAM_COLORS]
    return pool[hashBotId(botId) % pool.length]
  }
  return BEAM_COLORS[((index % BEAM_COLORS.length) + BEAM_COLORS.length) % BEAM_COLORS.length]
}

export function money(n: Money, signed = false): string {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  const abs = Math.abs(v).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: v % 1 === 0 ? 0 : 2,
  })
  if (!signed) return abs
  if (v > 0) return `+${abs}`
  if (v < 0) return `-${abs.replace('-', '')}`
  return abs
}

export function pnlTone(n: Money): 'up' | 'down' | 'flat' {
  if (n == null || Number(n) === 0) return 'flat'
  return Number(n) > 0 ? 'up' : 'down'
}

export function statusLabel(bot: BotRow): string {
  if (bot.present === false) return bot.empty || bot.why || 'offline'
  if (bot.paused) return 'paused'
  const bits = [bot.why, bot.skip, bot.idle_copy, bot.feed, bot.status].filter(
    (s) => typeof s === 'string' && s.trim(),
  ) as string[]
  return bits[0] || bot.status || 'idle'
}

/** Primary PnL figure shown on a tower hologram (today if nonzero, else realized). */
export function hologramPnlValue(bot: BotRow): number | null {
  if (bot.present === false) return null
  if (bot.today != null && bot.today !== 0) return Number(bot.today)
  if (bot.realized != null) return Number(bot.realized)
  return null
}

export function hologramPnl(bot: BotRow): string {
  if (bot.present === false) return 'offline'
  const raw = hologramPnlValue(bot)
  if (raw == null) return money(bot.cash)
  const label = bot.today != null && bot.today !== 0 ? 'today' : 'realized'
  return `${label} ${money(raw, true)}`
}

export function workersOnShift(bots: BotRow[] | undefined): number {
  return (bots || []).filter((b) => b.present && !b.paused).length
}

export function tradeLine(row: TradeOrHistory, botName?: string, includePnl = true): string {
  const when = row.when || row.closed_at || row.closed || ''
  const what = row.what || row.title || row.team || row.ticker || row.game || 'trade'
  const pnl = includePnl && row.pnl != null ? money(row.pnl, true) : ''
  const result = row.result || row.exit_reason || row.exit || ''
  return [botName, when, what, pnl, result].filter(Boolean).join(' · ')
}

export function flattenTicker(
  bots: BotRow[] | undefined,
  botId?: string | null,
): { text: string; pnl?: number | null }[] {
  const rows: { text: string; pnl?: number | null; sort?: string }[] = []
  for (const bot of bots || []) {
    if (botId && bot.id !== botId) continue
    const pool = [...(bot.history || []), ...(bot.trades || [])]
    for (const t of pool) {
      rows.push({
        // PnL rendered separately so the ticker can color red/green.
        text: tradeLine(t, bot.name, false),
        pnl: typeof t.pnl === 'number' ? t.pnl : null,
        sort: String(t.when || t.closed_at || t.closed || ''),
      })
    }
  }
  rows.sort((a, b) => String(b.sort).localeCompare(String(a.sort)))
  return rows.slice(0, 40).map(({ text, pnl }) => ({ text, pnl }))
}

/** Cumulative closed PnL sparkline from bot history, else desk curve. */
export function equitySeries(
  bot: BotRow | null | undefined,
  deskCurve?: { t?: string; v?: number }[],
): { x: number; y: number }[] {
  const hist = bot?.history || []
  if (hist.length) {
    let cum = 0
    return hist.map((h, i) => {
      cum += Number(h.pnl || 0)
      return { x: i, y: cum }
    })
  }
  const curve = deskCurve || []
  if (curve.length) {
    return curve.map((p, i) => ({ x: i, y: Number(p.v || 0) }))
  }
  return []
}
