import type { BotRow } from '../types'

/** Desk-bot animation modes driven by live snapshot fields. */
export type BotPose = 'trading' | 'waiting' | 'winning' | 'losing' | 'researching'

function textBlob(bot: BotRow): string {
  return [bot.status, bot.why, bot.skip, bot.idle_copy, bot.feed, bot.warning, bot.empty]
    .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
    .join(' ')
    .toLowerCase()
}

function lastSettledPnl(bot: BotRow): number | null {
  const rows = [...(bot.history || []), ...(bot.trades || [])]
  for (const row of rows) {
    if (typeof row.pnl === 'number' && Number.isFinite(row.pnl)) return row.pnl
  }
  return null
}

/**
 * Map a live BotRow to a visual pose. Never invents fills — only reads
 * present/paused/open/today/history/copy fields from the desk snapshot.
 */
export function botPose(bot: BotRow): BotPose {
  if (bot.present === false || bot.paused) return 'waiting'

  const blob = textBlob(bot)
  const open = Number(bot.open_count || 0)
  const today = typeof bot.today === 'number' ? bot.today : null
  const last = lastSettledPnl(bot)

  if (blob.includes('warn') || blob.includes('loss') || blob.includes('losing') || blob.includes('down')) {
    return 'losing'
  }
  if (typeof last === 'number' && last < 0 && open === 0) return 'losing'
  if (typeof today === 'number' && today < 0 && open === 0) return 'losing'

  if (
    blob.includes('win') ||
    blob.includes('paid') ||
    blob.includes('hit') ||
    (typeof today === 'number' && today > 0 && open === 0) ||
    (typeof last === 'number' && last > 0 && open === 0)
  ) {
    return 'winning'
  }

  if (open > 0 || blob.includes('trade') || blob.includes('fill') || blob.includes('entry') || blob.includes('exit')) {
    return 'trading'
  }

  if (
    blob.includes('research') ||
    blob.includes('watch') ||
    blob.includes('scan') ||
    blob.includes('skip') ||
    blob.includes('wait') ||
    blob.includes('idle') ||
    Boolean(bot.why || bot.skip || bot.idle_copy)
  ) {
    return 'researching'
  }

  if (bot.present) return 'researching'
  return 'waiting'
}
