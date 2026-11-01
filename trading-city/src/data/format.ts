import type { BotRow, Money, TradeOrHistory } from '../types'

export const BEAM_COLORS = ['#2de2e6', '#ff2a6d', '#39ff14', '#f9c80e', '#b967ff'] as const

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

export function hologramPnl(bot: BotRow): string {
  if (bot.present === false) return 'offline'
  const raw = bot.today != null && bot.today !== 0 ? bot.today : bot.realized
  if (raw == null) return money(bot.cash)
  const label = bot.today != null && bot.today !== 0 ? 'today' : 'realized'
  return `${label} ${money(raw, true)}`
}

export function workersOnShift(bots: BotRow[] | undefined): number {
  return (bots || []).filter((b) => b.present && !b.paused).length
}

export function tradeLine(row: TradeOrHistory, botName?: string): string {
  const when = row.when || row.closed_at || row.closed || ''
  const what = row.what || row.title || row.team || row.ticker || row.game || 'trade'
  const pnl = row.pnl != null ? money(row.pnl, true) : ''
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
        text: tradeLine(t, bot.name),
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
