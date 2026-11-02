import * as THREE from 'three'
import type { BotRow, Desk } from '../types'
import { equitySeries, money, statusLabel } from '../data/format'

const TEXTURE_SCALE = 4

function makeCanvas(w = 512, h = 384) {
  const canvas = document.createElement('canvas')
  canvas.width = w * TEXTURE_SCALE
  canvas.height = h * TEXTURE_SCALE
  const ctx = canvas.getContext('2d')!
  ctx.scale(TEXTURE_SCALE, TEXTURE_SCALE)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  return { canvas, ctx, w, h }
}

function screenTexture(canvas: HTMLCanvasElement) {
  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 16
  tex.minFilter = THREE.LinearFilter
  tex.magFilter = THREE.LinearFilter
  tex.generateMipmaps = false
  tex.needsUpdate = true
  return tex
}

function paintBase(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.fillStyle = '#050b14'
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = 'rgba(45,226,230,0.25)'
  ctx.strokeRect(2, 2, w - 4, h - 4)
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines = 4,
) {
  const words = text.split(/\s+/)
  let line = ''
  let lines = 0
  for (const word of words) {
    const test = line ? `${line} ${word}` : word
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y)
      line = word
      y += lineHeight
      lines += 1
      if (lines >= maxLines) return y
    } else {
      line = test
    }
  }
  if (line && lines < maxLines) ctx.fillText(line, x, y)
  return y + lineHeight
}

export function leftMonitorTexture(bot: BotRow): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas()
  paintBase(ctx, w, h)
  ctx.fillStyle = '#9aa3c7'
  ctx.font = '18px monospace'
  ctx.fillText(String(bot.status || 'status').toUpperCase(), 18, 32)
  ctx.fillText(bot.paused ? 'paused' : String(bot.feed || 'feed'), w - 18 - ctx.measureText(String(bot.feed || 'feed')).width, 32)

  ctx.fillStyle = '#f4f7ff'
  ctx.font = '20px monospace'
  let y = wrapText(ctx, statusLabel(bot), 18, 64, w - 36, 24, 3)

  ctx.fillStyle = '#2de2e6'
  ctx.font = '16px monospace'
  y = wrapText(
    ctx,
    `open ${bot.open_count ?? 0} · risk ${money(bot.open_risk)} · cash ${money(bot.cash)}`,
    18,
    y + 8,
    w - 36,
    20,
    2,
  )

  const positions = bot.positions || []
  ctx.fillStyle = '#39ff14'
  ctx.font = '15px monospace'
  if (bot.present === false) {
    wrapText(ctx, bot.empty || 'Not on this checkout.', 18, y + 12, w - 36, 18, 3)
  } else if (!positions.length) {
    ctx.fillStyle = '#9aa3c7'
    ctx.fillText('No open paper positions', 18, y + 28)
  } else {
    let yy = y + 24
    for (const p of positions.slice(0, 5)) {
      const label = p.what || p.title || p.team || p.ticker || 'position'
      ctx.fillStyle = '#39ff14'
      ctx.fillText(String(label).slice(0, 36), 18, yy)
      yy += 20
      ctx.fillStyle = '#9aa3c7'
      ctx.fillText(`${p.side || ''} ${money(p.cost)}`.trim().slice(0, 40), 18, yy)
      yy += 22
      if (yy > h - 20) break
    }
  }

  return screenTexture(canvas)
}

export function centerMonitorTexture(bot: BotRow, desk?: Desk): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas(560, 400)
  paintBase(ctx, w, h)
  const title =
    (bot.positions && bot.positions[0]?.ticker) ||
    (bot.positions && bot.positions[0]?.team) ||
    bot.name
  ctx.fillStyle = '#9aa3c7'
  ctx.font = '16px monospace'
  ctx.fillText(`${title} · equity`.slice(0, 42), 18, 30)
  const when = bot.central_check || bot.last_check || '—'
  ctx.fillText(String(when).slice(0, 28), w - 18 - ctx.measureText(String(when).slice(0, 28)).width, 30)

  const series = equitySeries(bot, desk?.curve || desk?.equity)
  const plotX = 24
  const plotY = 50
  const plotW = w - 48
  const plotH = 250
  ctx.fillStyle = 'rgba(20,40,80,0.35)'
  ctx.fillRect(plotX, plotY, plotW, plotH)

  if (!series.length) {
    ctx.fillStyle = '#9aa3c7'
    ctx.font = '18px monospace'
    ctx.fillText('No closed history yet', plotX + 40, plotY + plotH / 2)
  } else {
    const ys = series.map((p) => p.y)
    const min = Math.min(...ys, 0)
    const max = Math.max(...ys, 0)
    const span = max - min || 1
    const zeroY = plotY + plotH - ((0 - min) / span) * plotH
    ctx.strokeStyle = 'rgba(249,200,14,0.5)'
    ctx.beginPath()
    ctx.moveTo(plotX, zeroY)
    ctx.lineTo(plotX + plotW, zeroY)
    ctx.stroke()
    ctx.strokeStyle = '#f4f7ff'
    ctx.lineWidth = 2.5
    ctx.beginPath()
    series.forEach((p, i) => {
      const x = plotX + (i / Math.max(series.length - 1, 1)) * plotW
      const y = plotY + plotH - ((p.y - min) / span) * plotH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
  }

  ctx.fillStyle = '#9aa3c7'
  ctx.font = '15px monospace'
  ctx.fillText(`history ${bot.history?.length ?? 0}   VWAP/EMA cosmetic`, 18, h - 24)

  return screenTexture(canvas)
}

export function rightMonitorTexture(bot: BotRow): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas()
  paintBase(ctx, w, h)
  ctx.fillStyle = '#9aa3c7'
  ctx.font = '18px monospace'
  ctx.fillText('STATS', 18, 32)
  if (bot.next_run) ctx.fillText(String(bot.next_run).slice(0, 22), w - 160, 32)

  const today = Number(bot.today || 0)
  ctx.fillStyle = today >= 0 ? '#39ff14' : '#ff2a6d'
  ctx.font = 'bold 36px monospace'
  ctx.fillText(`today ${money(bot.today, true)}`, 18, 90)

  ctx.fillStyle = '#f4f7ff'
  ctx.font = '20px monospace'
  ctx.fillText(`realized ${money(bot.realized, true)}`, 18, 130)
  ctx.fillText(`bankroll ${money(bot.cash)}`, 18, 160)

  // Prefer closed/settled rows — open buys are not "last settled".
  const closedPool = [...(bot.history || []), ...(bot.trades || [])].filter((t) => {
    const side = String(t.side || '').toLowerCase()
    const exit = String(t.exit_reason || t.exit || t.result || '')
    if (side === 'buy') return false
    if (t.pnl != null) return true
    return Boolean(exit) && !/^buy\b/i.test(String(t.what || t.title || ''))
  })
  const last = closedPool.length ? closedPool[closedPool.length - 1] : null
  ctx.fillStyle = '#9aa3c7'
  ctx.font = '16px monospace'
  ctx.fillText('Last settled', 18, 210)
  if (last) {
    ctx.fillStyle = '#f4f7ff'
    ctx.font = '18px monospace'
    wrapText(ctx, String(last.what || last.title || last.team || last.ticker || 'trade'), 18, 240, w - 36, 22, 2)
    ctx.fillStyle = Number(last.pnl || 0) >= 0 ? '#39ff14' : '#ff2a6d'
    ctx.fillText(money(last.pnl, true), 18, 300)
    ctx.fillStyle = '#9aa3c7'
    ctx.font = '15px monospace'
    ctx.fillText(String(last.result || last.exit_reason || last.exit || '').slice(0, 40), 18, 330)
  } else {
    ctx.fillStyle = '#9aa3c7'
    ctx.fillText('No closed paper trades yet', 18, 250)
  }

  return screenTexture(canvas)
}

/** Wide bank lobby board — desk net profit / cash / pace. */
export function vaultBoardTexture(desk?: Desk): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas(1024, 220)
  ctx.fillStyle = '#050812'
  ctx.fillRect(0, 0, w, h)
  // subtle scanlines
  ctx.fillStyle = 'rgba(45,226,230,0.04)'
  for (let y = 0; y < h; y += 4) ctx.fillRect(0, y, w, 1)
  ctx.strokeStyle = 'rgba(249,200,14,0.65)'
  ctx.lineWidth = 3
  ctx.strokeRect(6, 6, w - 12, h - 12)
  ctx.strokeStyle = 'rgba(45,226,230,0.28)'
  ctx.lineWidth = 1
  ctx.strokeRect(12, 12, w - 24, h - 24)

  ctx.fillStyle = '#f9c80e'
  ctx.font = 'bold 26px monospace'
  ctx.fillText('APEX-CITY TRUST  ·  NET DESK', 28, 40)
  ctx.fillStyle = '#9aa3c7'
  ctx.font = '16px monospace'
  const clock = String(desk?.central_check || desk?.last_check || 'central clock pending').slice(0, 28)
  ctx.fillText(clock, w - 28 - ctx.measureText(clock).width, 40)

  const realized = Number(desk?.realized || 0)
  const today = Number(desk?.today || 0)
  ctx.fillStyle = realized >= 0 ? '#39ff14' : '#ff3b3b'
  ctx.font = 'bold 52px monospace'
  ctx.fillText(`realized ${money(desk?.realized, true)}`, 28, 105)

  ctx.fillStyle = today >= 0 ? '#39ff14' : '#ff3b3b'
  ctx.font = 'bold 34px monospace'
  ctx.fillText(`today ${money(desk?.today, true)}`, 28, 152)

  ctx.fillStyle = '#7ef9ff'
  ctx.font = '22px monospace'
  ctx.fillText(`cash ${money(desk?.cash)}`, 28, 192)

  ctx.fillStyle = '#b967ff'
  ctx.font = '18px monospace'
  const open = `open ${desk?.open_count ?? 0} · risk ${money(desk?.open_risk)}`
  ctx.fillText(open, 320, 192)

  if (desk?.pace_line) {
    const pace = String(desk.pace_line).slice(0, 34)
    ctx.fillStyle = '#9aa3c7'
    ctx.fillText(pace, w - 28 - ctx.measureText(pace).width, 192)
  }

  return screenTexture(canvas)
}

/** Left lobby wall — live desk ledger / teller cash strip. */
export function vaultLedgerTexture(desk?: Desk, bots: BotRow[] = []): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas(640, 400)
  paintBase(ctx, w, h)
  ctx.fillStyle = '#f9c80e'
  ctx.font = 'bold 22px monospace'
  ctx.fillText('DESK LEDGER', 22, 36)
  ctx.fillStyle = '#7ef9ff'
  ctx.font = '16px monospace'
  ctx.fillText(`vault cash ${money(desk?.cash)}`, 22, 62)
  ctx.fillStyle = '#9aa3c7'
  ctx.fillText(`open risk ${money(desk?.open_risk)} · positions ${desk?.open_count ?? 0}`, 22, 86)

  let y = 118
  ctx.font = '15px monospace'
  for (const bot of bots.slice(0, 5)) {
    const offline = bot.present === false
    ctx.fillStyle = offline ? '#6a5678' : '#f4f7ff'
    ctx.fillText(String(bot.name || bot.id).slice(0, 18), 22, y)
    ctx.fillStyle = offline ? '#6a5678' : Number(bot.today || 0) >= 0 ? '#39ff14' : '#ff2a6d'
    const figure = offline ? 'offline' : money(bot.today != null && bot.today !== 0 ? bot.today : bot.realized, true)
    ctx.fillText(figure, w - 22 - ctx.measureText(figure).width, y)
    y += 28
    ctx.fillStyle = '#3a4560'
    ctx.fillRect(22, y - 18, w - 44, 1)
  }

  ctx.fillStyle = '#2de2e6'
  ctx.font = '14px monospace'
  wrapText(ctx, desk?.status_line || desk?.pace_line || 'Paper reserve synced to snapshot.', 22, h - 40, w - 44, 18, 2)

  return screenTexture(canvas)
}

/** Teller pod nameplate — sharp canvas so lobby labels match office monitors. */
export function tellerPlateTexture(
  bot: BotRow | null,
  index: number,
  accent: string,
): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas(512, 160)
  ctx.fillStyle = '#050812'
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = accent
  ctx.lineWidth = 4
  ctx.strokeRect(4, 4, w - 8, h - 8)
  ctx.fillStyle = accent
  ctx.fillRect(4, 4, w - 8, 6)

  const offline = !bot || bot.present === false
  ctx.fillStyle = '#f4f7ff'
  ctx.font = 'bold 28px monospace'
  ctx.fillText(String(bot?.name || `Teller ${index + 1}`).slice(0, 22), 18, 52)

  ctx.fillStyle = offline ? '#6a5678' : '#9aa3c7'
  ctx.font = '18px monospace'
  ctx.fillText(offline ? 'vault dark' : String(bot?.id || ''), 18, 84)

  if (!offline && bot) {
    const figure = bot.today != null && bot.today !== 0 ? bot.today : bot.realized
    ctx.fillStyle = Number(figure || 0) >= 0 ? '#39ff14' : '#ff2a6d'
    ctx.font = 'bold 24px monospace'
    ctx.fillText(money(figure, true), 18, 128)
    ctx.fillStyle = '#7ef9ff'
    ctx.font = '16px monospace'
    const cash = `cash ${money(bot.cash)}`
    ctx.fillText(cash, w - 18 - ctx.measureText(cash).width, 128)
  } else {
    ctx.fillStyle = '#6a5678'
    ctx.font = '18px monospace'
    ctx.fillText('offline · no paper book', 18, 128)
  }

  return screenTexture(canvas)
}

/** Right lobby wall — ROI / paper compliance strip. */
export function vaultComplianceTexture(desk?: Desk, bots: BotRow[] = []): THREE.CanvasTexture {
  const { canvas, ctx, w, h } = makeCanvas(640, 400)
  paintBase(ctx, w, h)
  ctx.fillStyle = '#39ff14'
  ctx.font = 'bold 22px monospace'
  ctx.fillText('COMPLIANCE BAY', 22, 36)

  const roiOk = desk?.ops?.roi_ok
  ctx.fillStyle = roiOk === false ? '#ff2a6d' : '#39ff14'
  ctx.font = '18px monospace'
  ctx.fillText(roiOk === false ? 'ROI SYSTEM · gaps' : 'ROI SYSTEM · compliance ok', 22, 68)

  ctx.fillStyle = '#f9c80e'
  ctx.font = '15px monospace'
  ctx.fillText('PAPER ONLY · no wallet · no live orders', 22, 96)

  ctx.fillStyle = '#9aa3c7'
  ctx.font = '14px monospace'
  const gated = desk?.ops?.entry_gated_bots?.length ?? 0
  const strong = desk?.ops?.strong_exits?.length ?? 0
  const weak = desk?.ops?.weak_exits?.length ?? 0
  ctx.fillText(`entry gated ${gated} · strong exits ${strong} · weak ${weak}`, 22, 124)

  let y = 160
  ctx.font = '15px monospace'
  for (const bot of bots.slice(0, 5)) {
    const offline = bot.present === false
    const exit = bot.plans?.exit_quality || '—'
    ctx.fillStyle = offline ? '#6a5678' : '#f4f7ff'
    ctx.fillText(String(bot.id).slice(0, 14), 22, y)
    ctx.fillStyle = exit === 'strong' ? '#39ff14' : exit === 'weak' ? '#ff2a6d' : '#f9c80e'
    ctx.fillText(String(exit), 220, y)
    ctx.fillStyle = bot.plans?.entry_gated ? '#ff2a6d' : '#2de2e6'
    ctx.fillText(bot.plans?.entry_gated ? 'gated' : 'open', 340, y)
    y += 26
  }

  ctx.fillStyle = '#7ef9ff'
  ctx.font = '14px monospace'
  wrapText(
    ctx,
    desk?.gate || 'Desk gates live from snapshot — vault does not invent fills.',
    22,
    h - 42,
    w - 44,
    18,
    2,
  )

  return screenTexture(canvas)
}
