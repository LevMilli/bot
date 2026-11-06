import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { BotRow, TradeOrHistory } from '../types'
import { beamColorFor, hologramPnlValue, money } from '../data/format'

/**
 * One trade chart per side of the world, four at most.
 * Walls stay at the plaza edge. The face is a glass panel, so the city reads through it.
 */
const REACH = 24
const HEIGHT = 16

const UP = '#3dff7a'
const DOWN = '#ff3355'
const FLAT = '#d7e2ff'

type Edge = 'back' | 'right' | 'front' | 'left'

const WALLS: {
  edge: Edge
  position: [number, number, number]
  rot: number
  size: [number, number]
}[] = [
  { edge: 'back', position: [0, HEIGHT / 2, -REACH], rot: 0, size: [REACH * 2, HEIGHT] },
  { edge: 'right', position: [REACH, HEIGHT / 2, 0], rot: -Math.PI / 2, size: [REACH * 2, HEIGHT] },
  { edge: 'front', position: [0, HEIGHT / 2, REACH], rot: Math.PI, size: [REACH * 2, HEIGHT] },
  { edge: 'left', position: [-REACH, HEIGHT / 2, 0], rot: Math.PI / 2, size: [REACH * 2, HEIGHT] },
]

function rand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

function hashId(id: string) {
  let h = 2166136261
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Cumulative pnl when the book has a path; otherwise a signed wave that finishes on today's return. */
function seriesFor(bot: BotRow): { points: number[]; quoted: boolean } {
  const rows = (bot.history && bot.history.length ? bot.history : bot.trades) || []
  if (rows.length >= 2) {
    let run = 0
    const full = rows.map((row) => {
      run += Number(row.pnl || 0)
      return run
    })
    const points = full.length > 42 ? full.slice(-42) : full
    return { points, quoted: true }
  }
  const shown = hologramPnlValue(bot)
  const end = shown == null ? 0 : shown
  const seed = hashId(bot.id || bot.name || 'wall')
  const n = 36
  const raw: number[] = []
  let v = (rand(seed) - 0.45) * 0.35
  for (let i = 0; i < n; i++) {
    v += (rand(seed + i * 13) - 0.48) * 0.28
    if (rand(seed + i * 19) > 0.86) v += rand(seed + i * 3) > 0.5 ? 0.22 : -0.22
    raw.push(v)
  }
  const last = raw[n - 1] || 1
  const amp = Math.abs(end) > 1 ? Math.abs(end) * 0.62 : 1
  return {
    quoted: false,
    points: raw.map((p, i) => {
      const t = i / (n - 1)
      return (p - last) * amp * 0.85 + end * t
    }),
  }
}

function returnOf(bot: BotRow, last: number) {
  const shown = hologramPnlValue(bot)
  return shown == null ? last : shown
}

function tone(n: number) {
  if (n > 0.005) return UP
  if (n < -0.005) return DOWN
  return FLAT
}

function rowsOf(bot: BotRow): TradeOrHistory[] {
  return (bot.history && bot.history.length ? bot.history : bot.trades) || []
}

function signature(bot: BotRow) {
  const rows = rowsOf(bot)
  const tail = rows.length ? Number(rows[rows.length - 1].pnl || 0) : 0
  const pos = bot.positions?.[0]
  return [
    bot.id,
    bot.today,
    bot.realized,
    rows.length,
    tail,
    bot.name,
    bot.open_count,
    bot.expectancy_hit_rate,
    bot.expectancy,
    bot.cash,
    bot.avg_win,
    bot.avg_loss,
    bot.positions?.length,
    pos?.what || pos?.title || pos?.team,
  ].join('|')
}

function emaSeries(values: number[], period = 8): number[] {
  if (!values.length) return []
  const k = 2 / (period + 1)
  const out: number[] = []
  let prev = values[0]
  for (const value of values) {
    prev = value * k + prev * (1 - k)
    out.push(prev)
  }
  return out
}

function recordOf(rows: TradeOrHistory[]) {
  let wins = 0
  let losses = 0
  for (const row of rows) {
    if (row.pnl == null) continue
    const pnl = Number(row.pnl)
    if (pnl > 0.005) wins += 1
    else if (pnl < -0.005) losses += 1
  }
  return { wins, losses }
}

function ink(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  fill: string,
  weight = 6,
) {
  ctx.lineJoin = 'round'
  ctx.miterLimit = 2
  ctx.lineWidth = weight
  ctx.strokeStyle = 'rgba(4, 2, 18, 0.9)'
  ctx.strokeText(text, x, y)
  ctx.fillStyle = fill
  ctx.fillText(text, x, y)
}

function diamond(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, fill: string) {
  ctx.beginPath()
  ctx.moveTo(x, y - r)
  ctx.lineTo(x + r * 0.7, y)
  ctx.lineTo(x, y + r)
  ctx.lineTo(x - r * 0.7, y)
  ctx.closePath()
  ctx.fillStyle = fill
  ctx.fill()
}

/**
 * Glass chart: the photo's blue field, vertical dashes, left skyline, and a
 * glowing line, plus a scale, high/low, and the tower's own color.
 * `time` breathes the tip and walks a scan across the plot.
 */
function paintWall(canvas: HTMLCanvasElement, bot: BotRow, time: number) {
  const W = 1800
  const H = 600
  const ctx = canvas.getContext('2d')!
  ctx.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0)
  const seed = hashId(bot.id || bot.name || 'wall')
  const beam = beamColorFor(bot.id)
  const tapeTop = H - 112

  ctx.clearRect(0, 0, W, H)
  const sky = ctx.createLinearGradient(0, 0, W * 0.12, H)
  sky.addColorStop(0, 'rgba(14, 18, 96, 0.5)')
  sky.addColorStop(0.42, 'rgba(22, 52, 196, 0.6)')
  sky.addColorStop(1, 'rgba(32, 88, 240, 0.7)')
  ctx.fillStyle = sky
  ctx.fillRect(0, 0, W, H)
  ctx.fillStyle = beam
  ctx.fillRect(0, 0, 12, H)
  ctx.fillStyle = 'rgba(255,255,255,0.045)'
  for (let y = 0; y < H; y += 7) ctx.fillRect(0, y, W, 1)
  const sheen = (time * 48) % (H + 40)
  ctx.fillStyle = 'rgba(255,255,255,0.07)'
  ctx.fillRect(0, sheen - 20, W, 22)

  const ground = tapeTop - 4
  let bx = 0
  let bi = 0
  while (bx < W * 0.34) {
    const bw = 46 + rand(seed + bi * 5) * 78
    const bh = (ground - 150) * (0.28 + rand(seed + bi * 9 + 2) * 0.72)
    ctx.fillStyle = 'rgba(5, 3, 14, 0.9)'
    ctx.fillRect(bx, ground - bh, bw - 5, bh)
    ctx.fillStyle = 'rgba(236, 242, 255, 0.9)'
    for (let wy = ground - bh + 16; wy < ground - 14; wy += 20) {
      for (let wx = bx + 10; wx < bx + bw - 16; wx += 16) {
        if (rand(seed + wx * 3 + wy + bi) > 0.4) ctx.fillRect(wx, wy, 4, 6)
      }
    }
    bx += bw
    bi += 1
  }

  ctx.save()
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.72)'
  ctx.lineWidth = 3
  ctx.setLineDash([9, 20])
  for (let i = 1; i < 18; i++) {
    const x = (i / 18) * W
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, H)
    ctx.stroke()
  }
  ctx.restore()

  const series = seriesFor(bot)
  const points = series.points
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const plotL = 36
  const plotR = W - 168
  const plotT = 186
  const plotB = tapeTop - 16
  const yOf = (v: number) => plotB - ((v - min) / span) * (plotB - plotT)
  const xy = points.map((v, i) => ({
    x: plotL + (i / Math.max(points.length - 1, 1)) * (plotR - plotL),
    y: yOf(v),
    v,
  }))
  const zeroIn = min < 0 && max > 0
  const zeroY = yOf(0)

  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.16)'
  ctx.lineWidth = 2
  ctx.setLineDash([4, 14])
  for (let i = 0; i <= 3; i++) {
    const y = plotT + ((plotB - plotT) * i) / 3
    ctx.beginPath()
    ctx.moveTo(plotL, y)
    ctx.lineTo(plotR, y)
    ctx.stroke()
  }
  ctx.restore()
  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.42)'
  ctx.lineWidth = 2
  ctx.strokeRect(plotL, plotT, plotR - plotL, plotB - plotT)
  ctx.restore()

  if (zeroIn) {
    ctx.save()
    ctx.strokeStyle = 'rgba(255,255,255,0.7)'
    ctx.lineWidth = 2
    ctx.setLineDash([12, 10])
    ctx.beginPath()
    ctx.moveTo(plotL, zeroY)
    ctx.lineTo(plotR, zeroY)
    ctx.stroke()
    ctx.restore()
    ctx.font = '700 26px monospace'
    ink(ctx, '0', plotR + 14, zeroY + 8, '#ffffff', 5)
  }

  ctx.save()
  for (let i = 1; i < xy.length; i++) {
    const a = xy[i - 1]
    const b = xy[i]
    const up = b.v >= a.v
    const floor = zeroIn ? zeroY : plotB
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.lineTo(b.x, floor)
    ctx.lineTo(a.x, floor)
    ctx.closePath()
    ctx.fillStyle = up ? `${beam}55` : 'rgba(255, 51, 85, 0.28)'
    ctx.fill()
  }
  ctx.restore()

  const trace = (from: number, to: number) => {
    ctx.beginPath()
    for (let i = from; i <= to; i++) {
      const p = xy[i]
      if (i === from) ctx.moveTo(p.x, p.y)
      else ctx.lineTo(p.x, p.y)
    }
    ctx.stroke()
  }
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = `${beam}33`
  ctx.lineWidth = 56
  trace(0, xy.length - 1)
  ctx.strokeStyle = `${beam}88`
  ctx.lineWidth = 30
  trace(0, xy.length - 1)
  for (let i = 1; i < xy.length; i++) {
    ctx.strokeStyle = xy[i].v >= xy[i - 1].v ? beam : DOWN
    ctx.lineWidth = 12
    trace(i - 1, i)
  }
  ctx.strokeStyle = '#fff6ff'
  ctx.lineWidth = 3
  trace(0, xy.length - 1)

  const ema = emaSeries(points, 8)
  ctx.save()
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.setLineDash([12, 8])
  ctx.strokeStyle = 'rgba(255,255,255,0.92)'
  ctx.lineWidth = 3
  ctx.beginPath()
  ema.forEach((v, i) => {
    const x = xy[i].x
    const y = yOf(v)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()
  ctx.restore()
  const emaTip = ema[ema.length - 1]
  ctx.font = '700 22px sans-serif'
  ink(ctx, 'EMA', xy[xy.length - 1].x - 54, yOf(emaTip) - 12, '#ffffff', 4)

  for (let i = 0; i < xy.length; i += 2) {
    const p = xy[i]
    ctx.beginPath()
    ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2)
    ctx.fillStyle = xy[i].v >= (xy[i - 1]?.v ?? p.v) ? '#ffffff' : DOWN
    ctx.fill()
  }

  let hiI = 0
  let loI = 0
  xy.forEach((p, i) => {
    if (p.v > xy[hiI].v) hiI = i
    if (p.v < xy[loI].v) loI = i
  })
  ctx.font = '700 24px sans-serif'
  const mark = (i: number, label: string, color: string, above: boolean) => {
    const p = xy[i]
    diamond(ctx, p.x, p.y, 11, color)
    const ty = above ? Math.max(plotT + 8, p.y - 18) : Math.min(plotB - 6, p.y + 28)
    ink(ctx, label, p.x + 14, ty, color, 4)
  }
  if (series.quoted && hiI !== loI) {
    mark(hiI, 'HIGH', UP, true)
    mark(loI, 'LOW', DOWN, false)
  }

  const tip = xy[xy.length - 1]
  const lastStep = xy.length > 1 ? tip.v - xy[xy.length - 2].v : tip.v
  const tipColor = tone(lastStep)
  const pulse = 16 + Math.sin(time * 5.2) * 6
  const glow = ctx.createRadialGradient(tip.x, tip.y, 2, tip.x, tip.y, 30 + pulse)
  glow.addColorStop(0, 'rgba(255,255,255,0.95)')
  glow.addColorStop(0.45, tipColor)
  glow.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 30 + pulse, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 7, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  const scanX = plotL + ((time * 120) % (plotR - plotL))
  ctx.fillStyle = 'rgba(255,255,255,0.18)'
  ctx.fillRect(scanX, plotT, 3, plotB - plotT)
  const glint = xy[Math.floor(((time * 2.4) % xy.length + xy.length) % xy.length)]
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(glint.x, glint.y, 5, 0, Math.PI * 2)
  ctx.fill()

  ctx.textAlign = 'left'
  if (series.quoted) {
    ctx.font = '700 26px monospace'
    for (let i = 0; i <= 3; i++) {
      const v = max - (span * i) / 3
      const y = plotT + ((plotB - plotT) * i) / 3
      ink(ctx, money(v, true), plotR + 16, y + 8, 'rgba(255,255,255,0.92)', 4)
    }
  }

  const ret = returnOf(bot, tip.v)
  const retColor = tone(ret)
  const period = bot.today != null && bot.today !== 0 ? 'TODAY' : 'REALIZED'
  const name = (bot.name || 'trade').slice(0, 22)
  ctx.font = '700 58px sans-serif'
  ink(ctx, name, 32, 64, '#ffffff', 8)
  const nameW = ctx.measureText(name).width
  const liveOn = Math.sin(time * 4) > 0
  ctx.beginPath()
  ctx.arc(32 + nameW + 28, 46, 10, 0, Math.PI * 2)
  ctx.fillStyle = liveOn ? retColor : 'rgba(255,255,255,0.35)'
  ctx.fill()

  ctx.font = '700 28px monospace'
  ink(ctx, '1W', 32 + nameW + 52, 40, DOWN, 4)
  ink(ctx, period, 32 + nameW + 52, 72, 'rgba(255,255,255,0.8)', 4)
  ctx.font = '700 64px monospace'
  const figure = money(ret, true)
  ink(ctx, figure, W - 36 - ctx.measureText(figure).width, 72, retColor, 8)

  ctx.font = '600 26px sans-serif'
  const rows = rowsOf(bot)
  const record = recordOf(rows)
  const last = [...rows].reverse().find((row) => row.pnl != null)
  const row1: { text: string; color: string }[] = [
    { text: `OPEN ${bot.open_count ?? 0}`, color: '#ffffff' },
  ]
  if (record.wins + record.losses > 0) {
    row1.push({ text: `${record.wins}W`, color: UP })
    row1.push({ text: `${record.losses}L`, color: DOWN })
  }
  if (bot.cash != null) row1.push({ text: `CASH ${money(bot.cash)}`, color: '#ffffff' })
  if (bot.expectancy_hit_rate != null && (bot.expectancy_n ?? 0) > 0) {
    row1.push({ text: `HIT ${Math.round(bot.expectancy_hit_rate * 100)}%`, color: '#ffffff' })
  }
  if (bot.expectancy != null && (bot.expectancy_n ?? 0) > 0) {
    row1.push({ text: `EXP ${money(bot.expectancy, true)}`, color: tone(bot.expectancy) })
  }
  const row2: { text: string; color: string }[] = []
  if (series.quoted) {
    row2.push({ text: `HIGH ${money(max, true)}`, color: UP })
    row2.push({ text: `LOW ${money(min, true)}`, color: DOWN })
    row2.push({ text: `PATH ${money(points[points.length - 1] - points[0], true)}`, color: tone(points[points.length - 1] - points[0]) })
  }
  if (bot.avg_win != null) row2.push({ text: `AVG W ${money(bot.avg_win, true)}`, color: UP })
  if (bot.avg_loss != null) row2.push({ text: `AVG L ${money(bot.avg_loss, true)}`, color: DOWN })
  const pos = bot.positions?.[0]
  if (pos) {
    const side = pos.side ? String(pos.side).toUpperCase() : 'IN'
    const what = String(pos.what || pos.title || pos.team || pos.ticker || 'position').slice(0, 18)
    row2.push({ text: `${side} ${what}`, color: beam })
  }
  if (last) {
    const what = String(last.what || last.title || last.team || last.ticker || 'last').slice(0, 20)
    row2.push({ text: `${what} ${money(last.pnl, true)}`, color: tone(Number(last.pnl || 0)) })
  }
  const paintRow = (items: { text: string; color: string }[], y: number) => {
    let x = 32
    for (const chip of items) {
      const w = ctx.measureText(chip.text).width
      if (x + w > W - 36) break
      ink(ctx, chip.text, x, y, chip.color, 5)
      x += w + 26
    }
  }
  paintRow(row1, 114)
  paintRow(row2, 150)

  ctx.fillStyle = 'rgba(4, 2, 18, 0.45)'
  ctx.fillRect(0, tapeTop, W, H - tapeTop)
  ctx.fillStyle = beam
  ctx.fillRect(0, tapeTop, W, 4)
  const prints = rows.slice(-16)
  const recent = [...rows].reverse().filter((row) => row.pnl != null).slice(0, 2)
  const textX = W * 0.58
  ctx.font = '700 22px sans-serif'
  ink(ctx, 'PRINTS', 24, tapeTop + 32, 'rgba(255,255,255,0.85)', 4)
  if (prints.length) {
    const absMax = Math.max(...prints.map((row) => Math.abs(Number(row.pnl || 0))), 1)
    const slot = (textX - 170) / prints.length
    prints.forEach((row, i) => {
      const pnl = Number(row.pnl || 0)
      const bh = Math.max(8, (Math.abs(pnl) / absMax) * 64)
      const x = 140 + i * slot
      ctx.fillStyle = tone(pnl)
      ctx.fillRect(x, tapeTop + 96 - bh, Math.max(8, slot - 8), bh)
    })
  } else {
    ctx.font = '600 24px sans-serif'
    ink(ctx, 'no closed prints yet', 140, tapeTop + 72, 'rgba(255,255,255,0.75)', 4)
  }
  ctx.font = '700 26px sans-serif'
  recent.forEach((row, i) => {
    const what = String(row.what || row.title || row.team || row.ticker || 'trade').slice(0, 26)
    ink(ctx, `${what}  ${money(row.pnl, true)}`, textX, tapeTop + 42 + i * 34, tone(Number(row.pnl || 0)), 4)
  })

  const tag = figure
  ctx.font = '700 36px monospace'
  const step = series.quoted ? money(lastStep, true) : ''
  const tagW = Math.max(ctx.measureText(tag).width, step ? ctx.measureText(step).width : 0) + 32
  let tagX = tip.x + 22
  if (tagX + tagW > plotR - 4) tagX = tip.x - tagW - 18
  const tagH = step ? 78 : 48
  let tagY = tip.y - tagH - 12
  tagY = Math.min(Math.max(tagY, plotT + 4), plotB - tagH - 4)
  ctx.fillStyle = 'rgba(4, 2, 18, 0.62)'
  ctx.fillRect(tagX, tagY, tagW, tagH)
  ctx.fillStyle = retColor
  ctx.fillRect(tagX, tagY, 6, tagH)
  ink(ctx, tag, tagX + 16, tagY + 34, retColor, 5)
  if (step) {
    ctx.font = '700 24px monospace'
    ink(ctx, step, tagX + 16, tagY + 64, tone(lastStep), 4)
  }

  ctx.save()
  ctx.strokeStyle = beam
  ctx.lineWidth = 5
  const arm = 42
  const m = 12
  const corners: [number, number, number, number][] = [
    [m, m, 1, 1],
    [W - m, m, -1, 1],
    [m, H - m, 1, -1],
    [W - m, H - m, -1, -1],
  ]
  for (const [x, y, sx, sy] of corners) {
    ctx.beginPath()
    ctx.moveTo(x + arm * sx, y)
    ctx.lineTo(x, y)
    ctx.lineTo(x, y + arm * sy)
    ctx.stroke()
  }
  ctx.restore()
}

function TradeWall({ bot, edge }: { bot: BotRow; edge: Edge }) {
  const wall = WALLS.find((w) => w.edge === edge)!
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const state = useRef({ acc: 0, sig: '', time: 0 })
  const map = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 2400
    canvas.height = 800
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    tex.anisotropy = 8
    tex.userData.canvas = canvas
    paintWall(canvas, bot, 0)
    tex.needsUpdate = true
    return tex
  }, [bot.id])

  useEffect(() => () => map.dispose(), [map])

  useFrame((_, dt) => {
    const canvas = map.userData.canvas as HTMLCanvasElement | undefined
    if (!canvas) return
    const st = state.current
    st.time += dt
    st.acc += dt
    const sig = signature(bot)
    const dataChanged = sig !== st.sig
    if (!dataChanged && (reduced || st.acc < 0.12)) return
    st.acc = 0
    st.sig = sig
    paintWall(canvas, bot, reduced ? 0 : st.time)
    map.needsUpdate = true
  })

  return (
    <group position={wall.position} rotation={[0, wall.rot, 0]} raycast={() => null}>
      <mesh position={[0, 0, 0]}>
        <planeGeometry args={[wall.size[0], wall.size[1]]} />
        <meshBasicMaterial
          map={map}
          transparent
          depthWrite={false}
          toneMapped={false}
          fog={false}
          side={THREE.FrontSide}
        />
      </mesh>
    </group>
  )
}

/** Four world-edge walls. Each one is a single trade chart, and there are never more than four. */
export function BorderScreens({ bots }: { bots: BotRow[] }) {
  const live = bots.filter((b) => b.present !== false)
  const shown = (live.length ? live : bots).slice(0, 4)
  return (
    <group>
      {shown.map((bot, i) => (
        <TradeWall key={bot.id} bot={bot} edge={WALLS[i].edge} />
      ))}
    </group>
  )
}
