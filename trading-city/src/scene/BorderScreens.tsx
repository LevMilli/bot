import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { BotRow } from '../types'
import { hologramPnlValue, money } from '../data/format'

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
 * Glass chart in the reference photo: a see-through blue field, vertical
 * dashes, a left skyline, and one thick magenta line with a white tip.
 * `time` only breathes the tip.
 */
function paintWall(canvas: HTMLCanvasElement, bot: BotRow, time: number) {
  const W = canvas.width
  const H = canvas.height
  const ctx = canvas.getContext('2d')!
  const seed = hashId(bot.id || bot.name || 'wall')

  ctx.clearRect(0, 0, W, H)
  const sky = ctx.createLinearGradient(0, 0, W * 0.12, H)
  sky.addColorStop(0, 'rgba(14, 18, 96, 0.5)')
  sky.addColorStop(0.42, 'rgba(22, 52, 196, 0.6)')
  sky.addColorStop(1, 'rgba(32, 88, 240, 0.7)')
  ctx.fillStyle = sky
  ctx.fillRect(0, 0, W, H)

  const ground = H - 2
  let bx = 0
  let bi = 0
  while (bx < W * 0.38) {
    const bw = 46 + rand(seed + bi * 5) * 78
    const bh = H * (0.22 + rand(seed + bi * 9 + 2) * 0.5)
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
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.88)'
  ctx.lineWidth = 3
  ctx.setLineDash([9, 20])
  for (let i = 1; i < 15; i++) {
    const x = (i / 15) * W
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, H)
    ctx.stroke()
  }
  ctx.restore()

  const points = seriesFor(bot)
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const plotL = 36
  const plotR = W * 0.7
  const plotT = H * 0.16
  const plotB = H * 0.78
  const xy = points.map((v, i) => ({
    x: plotL + (i / Math.max(points.length - 1, 1)) * (plotR - plotL),
    y: plotB - ((v - min) / span) * (plotB - plotT),
    v,
  }))

  ctx.beginPath()
  xy.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
  ctx.lineTo(xy[xy.length - 1].x, H)
  ctx.lineTo(xy[0].x, H)
  ctx.closePath()
  const wash = ctx.createLinearGradient(0, plotT, 0, H)
  wash.addColorStop(0, 'rgba(255, 70, 220, 0.28)')
  wash.addColorStop(1, 'rgba(80, 20, 160, 0)')
  ctx.fillStyle = wash
  ctx.fill()

  const stroke = () => {
    ctx.beginPath()
    xy.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
    ctx.stroke()
  }
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = 'rgba(255, 170, 255, 0.55)'
  ctx.lineWidth = 36
  stroke()
  ctx.strokeStyle = '#ff3ad4'
  ctx.lineWidth = 14
  stroke()
  ctx.strokeStyle = '#ffe6ff'
  ctx.lineWidth = 4
  stroke()

  const tip = xy[xy.length - 1]
  const pulse = 18 + Math.sin(time * 5.2) * 6
  const glow = ctx.createRadialGradient(tip.x, tip.y, 2, tip.x, tip.y, 28 + pulse)
  glow.addColorStop(0, 'rgba(255,255,255,0.95)')
  glow.addColorStop(0.4, 'rgba(255,180,255,0.55)')
  glow.addColorStop(1, 'rgba(255,60,210,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 28 + pulse, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 7, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  const ret = returnOf(bot, tip.v)
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = '600 34px sans-serif'
  ctx.fillText((bot.name || 'trade').slice(0, 18), 28, 48)
  ctx.fillStyle = DOWN
  ctx.font = 'bold 32px monospace'
  ctx.fillText('1W', W * 0.4, 46)
  ctx.fillStyle = tone(ret)
  ctx.font = 'bold 40px monospace'
  ctx.fillText(money(ret, true), W * 0.4, 92)
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
