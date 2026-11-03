import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { BotRow } from '../types'
import { hologramPnlValue, money } from '../data/format'

/**
 * One trade chart per side of the world, four at most.
 * The box sits outside the farthest camera orbit so zoom-out still looks at the inner face.
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
function seriesFor(bot: BotRow): number[] {
  const rows = (bot.history && bot.history.length ? bot.history : bot.trades) || []
  if (rows.length >= 2) {
    let run = 0
    const full = rows.map((row) => {
      run += Number(row.pnl || 0)
      return run
    })
    return full.length > 42 ? full.slice(-42) : full
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
  const amp = Math.max(Math.abs(end), 48)
  return raw.map((p, i) => {
    const t = i / (n - 1)
    return (p - last) * amp * 0.85 + end * t
  })
}

function returnOf(bot: BotRow, last: number) {
  const shown = hologramPnlValue(bot)
  return shown == null ? last : shown
}

function periodOf(bot: BotRow) {
  return bot.today != null && bot.today !== 0 ? 'TODAY' : 'REALIZED'
}

function tone(n: number) {
  if (n > 0.005) return UP
  if (n < -0.005) return DOWN
  return FLAT
}

function signature(bot: BotRow) {
  const rows = (bot.history && bot.history.length ? bot.history : bot.trades) || []
  const tail = rows.length ? Number(rows[rows.length - 1].pnl || 0) : 0
  return `${bot.id}|${bot.today}|${bot.realized}|${rows.length}|${tail}|${bot.name}`
}

/**
 * Blue wall chart: dashed grid, left skyline, and a line that is green on the
 * way up and red on the way down. `time` drives the live tip and scan.
 */
function paintWall(canvas: HTMLCanvasElement, bot: BotRow, time: number) {
  const W = canvas.width
  const H = canvas.height
  const ctx = canvas.getContext('2d')!
  const seed = hashId(bot.id || bot.name || 'wall')

  const sky = ctx.createLinearGradient(0, 0, W * 0.25, H)
  sky.addColorStop(0, '#0e0848')
  sky.addColorStop(0.4, '#1730b4')
  sky.addColorStop(1, '#1c4ae6')
  ctx.fillStyle = sky
  ctx.fillRect(0, 0, W, H)

  const ground = H - 2
  let bx = 0
  let bi = 0
  while (bx < W * 0.36) {
    const bw = 48 + rand(seed + bi * 5) * 86
    const bh = H * (0.18 + rand(seed + bi * 9 + 2) * 0.46)
    ctx.fillStyle = '#070512'
    ctx.fillRect(bx, ground - bh, bw - 6, bh)
    ctx.fillStyle = '#eef3ff'
    for (let wy = ground - bh + 18; wy < ground - 16; wy += 22) {
      for (let wx = bx + 12; wx < bx + bw - 18; wx += 18) {
        if (rand(seed + wx * 3 + wy + bi) > 0.42) ctx.fillRect(wx, wy, 6, 8)
      }
    }
    bx += bw
    bi += 1
  }

  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.72)'
  ctx.lineWidth = 3
  ctx.setLineDash([14, 22])
  for (let i = 1; i < 16; i++) {
    const x = (i / 16) * W
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, H)
    ctx.stroke()
  }
  ctx.strokeStyle = 'rgba(255,255,255,0.22)'
  ctx.lineWidth = 2
  ctx.setLineDash([8, 18])
  for (let i = 1; i < 7; i++) {
    const y = (i / 7) * H
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(W, y)
    ctx.stroke()
  }
  ctx.restore()

  const points = seriesFor(bot)
  let min = Math.min(...points, 0)
  let max = Math.max(...points, 0)
  const pad = (max - min) * 0.14 || 1
  min -= pad
  max += pad
  const span = max - min || 1
  const plotL = 48
  const plotR = W * 0.78
  const plotT = H * 0.4
  const plotB = H * 0.9
  const yOf = (v: number) => plotB - ((v - min) / span) * (plotB - plotT)
  const xy = points.map((v, i) => ({
    x: plotL + (i / Math.max(points.length - 1, 1)) * (plotR - plotL),
    y: yOf(v),
    v,
  }))
  const zeroY = yOf(0)

  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.55)'
  ctx.lineWidth = 2
  ctx.setLineDash([10, 12])
  ctx.beginPath()
  ctx.moveTo(plotL, zeroY)
  ctx.lineTo(plotR + 36, zeroY)
  ctx.stroke()
  ctx.restore()
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = '700 36px sans-serif'
  ctx.fillText('0', plotR + 16, zeroY + 12)

  for (let i = 1; i < xy.length; i++) {
    const a = xy[i - 1]
    const b = xy[i]
    const up = b.v >= a.v
    const color = up ? UP : DOWN
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.lineTo(b.x, zeroY)
    ctx.lineTo(a.x, zeroY)
    ctx.closePath()
    ctx.fillStyle = up ? 'rgba(61,255,122,0.16)' : 'rgba(255,51,85,0.16)'
    ctx.fill()
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.strokeStyle = up ? 'rgba(120,255,170,0.55)' : 'rgba(255,90,110,0.55)'
    ctx.lineWidth = 28
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.stroke()
    ctx.strokeStyle = color
    ctx.lineWidth = 12
    ctx.stroke()
    ctx.strokeStyle = 'rgba(255,255,255,0.92)'
    ctx.lineWidth = 3
    ctx.stroke()
  }

  const tip = xy[xy.length - 1]
  const lastStep = xy.length > 1 ? tip.v - xy[xy.length - 2].v : tip.v
  const tipColor = tone(lastStep)
  const pulse = 16 + Math.sin(time * 5.5) * 7
  const glow = ctx.createRadialGradient(tip.x, tip.y, 2, tip.x, tip.y, 36 + pulse)
  glow.addColorStop(0, 'rgba(255,255,255,0.95)')
  glow.addColorStop(0.35, tipColor)
  glow.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 36 + pulse, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 8, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  const scanX = plotL + ((time * 90) % (plotR - plotL))
  ctx.fillStyle = 'rgba(255,255,255,0.14)'
  ctx.fillRect(scanX, plotT - 20, 3, plotB - plotT + 40)

  const ret = returnOf(bot, tip.v)
  const retColor = tone(ret)
  const word = ret > 0.005 ? 'UP' : ret < -0.005 ? 'DOWN' : 'FLAT'
  const figure = money(ret, true)
  ctx.fillStyle = 'rgba(4,2,16,0.82)'
  ctx.fillRect(0, 0, W, 118)
  ctx.fillStyle = retColor
  ctx.fillRect(0, 114, W, 6)
  ctx.fillStyle = '#ffffff'
  ctx.font = '700 58px sans-serif'
  ctx.fillText((bot.name || 'trade').slice(0, 16), 28, 74)
  ctx.font = '800 28px sans-serif'
  ctx.fillStyle = retColor
  ctx.fillText(word, 620, 42)
  ctx.font = '700 54px monospace'
  ctx.fillText(figure, 620, 96)
  const figureW = ctx.measureText(figure).width
  ctx.fillStyle = 'rgba(255,255,255,0.72)'
  ctx.font = '600 24px sans-serif'
  ctx.fillText(periodOf(bot), 620 + figureW + 18, 90)
  const liveOn = Math.sin(time * 4) > 0
  ctx.fillStyle = liveOn ? retColor : 'rgba(255,255,255,0.35)'
  ctx.beginPath()
  ctx.arc(W - 148, 58, 11, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#ffffff'
  ctx.font = '700 32px sans-serif'
  ctx.fillText('LIVE', W - 124, 70)

  ctx.font = '700 32px monospace'
  const tag = figure
  const tagW = ctx.measureText(tag).width + 28
  const tagX = tip.x + 18 + tagW > W - 12 ? tip.x - tagW - 16 : tip.x + 18
  const tagY = Math.min(Math.max(tip.y - 22, 132), H - 56)
  ctx.fillStyle = 'rgba(4,2,16,0.88)'
  ctx.fillRect(tagX, tagY, tagW, 44)
  ctx.fillStyle = retColor
  ctx.fillRect(tagX, tagY, 6, 44)
  ctx.fillStyle = '#ffffff'
  ctx.fillText(tag, tagX + 16, tagY + 31)
}

function TradeWall({ bot, edge }: { bot: BotRow; edge: Edge }) {
  const wall = WALLS.find((w) => w.edge === edge)!
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const state = useRef({ acc: 0, sig: '', time: 0 })
  const map = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1800
    canvas.height = 600
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
        <meshBasicMaterial map={map} toneMapped={false} fog={false} side={THREE.FrontSide} />
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
