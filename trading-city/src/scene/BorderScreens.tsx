import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import type { BotRow } from '../types'
import { money } from '../data/format'

/**
 * One trade chart per side of the world, four at most.
 * The box sits outside the farthest camera orbit (radius ~31) so the
 * view stays on the inner face, and in front of the far skyline.
 */
const REACH = 24
const HEIGHT = 16

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

/** Cumulative pnl when the book has a real path; otherwise a jagged wall-chart shape. */
function seriesFor(bot: BotRow): number[] {
  const rows = (bot.history && bot.history.length ? bot.history : bot.trades) || []
  if (rows.length >= 2) {
    let run = 0
    return rows.map((row) => {
      run += Number(row.pnl || 0)
      return run
    })
  }
  const end = Number(bot.today || bot.realized || 0)
  const seed = hashId(bot.id || bot.name || 'wall')
  const n = 32
  const out: number[] = []
  let v = 0.86 + rand(seed) * 0.08
  for (let i = 0; i < n; i++) {
    const kick = (rand(seed + i * 17) - 0.38) * 0.16
    v += kick - 0.018
    if (rand(seed + i * 29) > 0.84) v -= 0.14 + rand(seed + i) * 0.08
    if (rand(seed + i * 11) > 0.9) v += 0.1
    v = Math.max(0.12, Math.min(0.96, v))
    out.push(v)
  }
  const scale = end === 0 ? 180 + rand(seed + 4) * 220 : end
  const last = out[out.length - 1] || 1
  return out.map((p) => (p / last) * scale)
}

/**
 * Full-bleed wall in the reference style: royal-blue field, dashed vertical
 * grid, a windowed skyline on the left, and one thick magenta trade line.
 */
function paintWall(bot: BotRow): THREE.CanvasTexture {
  const W = 2048
  const H = 1080
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  const seed = hashId(bot.id || bot.name || 'wall')

  const sky = ctx.createLinearGradient(0, 0, W * 0.3, H)
  sky.addColorStop(0, '#120a55')
  sky.addColorStop(0.42, '#1a32b8')
  sky.addColorStop(1, '#1d4ae0')
  ctx.fillStyle = sky
  ctx.fillRect(0, 0, W, H)

  const ground = H - 2
  let bx = 0
  let bi = 0
  const zone = W * 0.4
  while (bx < zone) {
    const bw = 54 + rand(seed + bi * 5) * 92
    const bh = H * (0.22 + rand(seed + bi * 9 + 2) * 0.52)
    ctx.fillStyle = '#070512'
    ctx.fillRect(bx, ground - bh, bw - 6, bh)
    ctx.fillStyle = '#eef3ff'
    const win = 7
    for (let wy = ground - bh + 22; wy < ground - 18; wy += 26) {
      for (let wx = bx + 14; wx < bx + bw - 22; wx += 20) {
        if (rand(seed + wx * 3 + wy + bi) > 0.38) ctx.fillRect(wx, wy, win, win + 3)
      }
    }
    bx += bw
    bi += 1
  }

  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.8)'
  ctx.lineWidth = 4
  ctx.setLineDash([16, 26])
  const cols = 15
  for (let i = 1; i < cols; i++) {
    const x = (i / cols) * W
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
  const plotL = 48
  const plotR = W * 0.7
  const plotT = H * 0.18
  const plotB = H * 0.8
  const xy = points.map((v, i) => {
    const x = plotL + (i / Math.max(points.length - 1, 1)) * (plotR - plotL)
    const y = plotB - ((v - min) / span) * (plotB - plotT)
    return { x, y }
  })

  ctx.beginPath()
  xy.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
  ctx.lineTo(xy[xy.length - 1].x, H)
  ctx.lineTo(xy[0].x, H)
  ctx.closePath()
  const fill = ctx.createLinearGradient(0, plotT, 0, H)
  fill.addColorStop(0, 'rgba(255,70,230,0.28)')
  fill.addColorStop(1, 'rgba(40,10,120,0.02)')
  ctx.fillStyle = fill
  ctx.fill()

  const stroke = () => {
    ctx.beginPath()
    xy.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)))
    ctx.stroke()
  }
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = 'rgba(255,150,255,0.45)'
  ctx.lineWidth = 54
  stroke()
  ctx.strokeStyle = '#ff3ad6'
  ctx.lineWidth = 22
  stroke()
  ctx.strokeStyle = '#ffe8ff'
  ctx.lineWidth = 6
  stroke()

  const tip = xy[xy.length - 1]
  const glow = ctx.createRadialGradient(tip.x, tip.y, 4, tip.x, tip.y, 54)
  glow.addColorStop(0, 'rgba(255,255,255,0.95)')
  glow.addColorStop(0.35, 'rgba(255,220,255,0.55)')
  glow.addColorStop(1, 'rgba(255,80,220,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 54, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(tip.x, tip.y, 12, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  const last = points[points.length - 1]
  ctx.fillStyle = '#ff3355'
  ctx.font = 'bold 54px monospace'
  ctx.fillText('1W', W * 0.4, H * 0.15)
  ctx.font = 'bold 46px monospace'
  ctx.fillText(money(last, true), W * 0.4, H * 0.15 + 54)
  ctx.fillStyle = 'rgba(255,255,255,0.94)'
  ctx.font = '600 42px sans-serif'
  ctx.fillText((bot.name || 'trade').slice(0, 20), 56, H * 0.15)

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  tex.needsUpdate = true
  return tex
}

function TradeWall({ bot, edge }: { bot: BotRow; edge: Edge }) {
  const wall = WALLS.find((w) => w.edge === edge)!
  const map = useMemo(() => paintWall(bot), [bot])
  useEffect(() => () => map.dispose(), [map])

  return (
    <group position={wall.position} rotation={[0, wall.rot, 0]} raycast={() => null}>
      <mesh position={[0, 0, -0.12]}>
        <boxGeometry args={[wall.size[0], wall.size[1], 0.18]} />
        <meshBasicMaterial color="#07061a" />
      </mesh>
      <mesh position={[0, 0, 0.02]}>
        <planeGeometry args={[wall.size[0], wall.size[1]]} />
        <meshBasicMaterial map={map} toneMapped={false} fog={false} />
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
