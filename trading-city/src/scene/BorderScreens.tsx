import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Mesh } from 'three'
import type { BotRow } from '../types'
import { beamColorFor, hologramPnl, statusLabel } from '../data/format'
import { BACK_ROAD_HALF_W, BACK_ROAD_Z } from './plazaLayout'

type Edge = 'back' | 'right' | 'front' | 'left'

const EDGES: Edge[] = ['back', 'right', 'front', 'left']

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Share the towers across the four city walls. */
function countsFor(n: number): number[] {
  if (n <= 0) return [0, 0, 0, 0]
  const weight = [1.15, 0.85, 1.15, 0.85]
  const sum = weight.reduce((a, b) => a + b, 0)
  const raw = weight.map((w) => (n * w) / sum)
  const base = raw.map((v) => Math.floor(v))
  let left = n - base.reduce((a, b) => a + b, 0)
  const order = raw
    .map((v, i) => ({ i, f: v - base[i] }))
    .sort((a, b) => b.f - a.f)
  for (let k = 0; k < left; k++) base[order[k % order.length].i] += 1
  return base
}

function place(edge: Edge, index: number, count: number) {
  const t = (index + 0.5) / count
  if (edge === 'back') return { x: -13 + t * 26, z: BACK_ROAD_Z - BACK_ROAD_HALF_W - 4.3, rot: 0 }
  if (edge === 'front') return { x: 13 - t * 26, z: 15.4, rot: Math.PI }
  if (edge === 'right') return { x: 17.6, z: -6.2 + t * 18.4, rot: -Math.PI / 2 }
  return { x: -17.6, z: 12.2 - t * 18.4, rot: Math.PI / 2 }
}

function paintScreen(bot: BotRow, index: number, color: string) {
  const w = 512
  const h = 768
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#07061a'
  ctx.fillRect(0, 0, w, h)

  ctx.strokeStyle = color
  ctx.lineWidth = 10
  ctx.strokeRect(16, 16, w - 32, h - 32)

  ctx.strokeStyle = 'rgba(255,255,255,0.06)'
  ctx.lineWidth = 1
  for (let y = 80; y < h; y += 28) {
    ctx.beginPath()
    ctx.moveTo(36, y)
    ctx.lineTo(w - 36, y)
    ctx.stroke()
  }

  ctx.fillStyle = color
  ctx.font = 'bold 28px monospace'
  ctx.fillText(bot.present === false ? 'OFFLINE' : 'LIVE TOWER', 40, 72)

  ctx.fillStyle = '#f4f0ff'
  ctx.font = 'bold 46px sans-serif'
  const name = bot.name.length > 16 ? `${bot.name.slice(0, 15)}…` : bot.name
  ctx.fillText(name, 40, 140)

  ctx.fillStyle = color
  ctx.font = '32px monospace'
  ctx.fillText(hologramPnl(bot), 40, 196)

  ctx.fillStyle = '#9aa3c7'
  ctx.font = '22px monospace'
  const line = statusLabel(bot).slice(0, 42)
  wrapText(ctx, line, 40, 250, w - 80, 30)

  // Tower silhouette so the panel reads as that building.
  const bx = w / 2
  const base = 700
  const bh = 210
  const bw = 140
  ctx.fillStyle = color
  ctx.globalAlpha = 0.85
  ctx.fillRect(bx - bw / 2, base - bh, bw, bh)
  ctx.fillRect(bx - 18, base - bh - 70, 36, 70)
  ctx.globalAlpha = 0.35
  ctx.fillStyle = '#fff6c8'
  for (let row = 0; row < 7; row++) {
    for (let col = 0; col < 3; col++) {
      if ((row + col + index) % 3 === 0) continue
      ctx.fillRect(bx - bw / 2 + 22 + col * 40, base - bh + 24 + row * 36, 16, 18)
    }
  }
  ctx.globalAlpha = 1

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.needsUpdate = true
  return tex
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxW: number,
  lineH: number,
) {
  const words = text.split(' ')
  let line = ''
  let cy = y
  for (const word of words) {
    const next = line ? `${line} ${word}` : word
    if (ctx.measureText(next).width > maxW && line) {
      ctx.fillText(line, x, cy)
      line = word
      cy += lineH
      if (cy > y + lineH * 2) break
    } else {
      line = next
    }
  }
  if (line && cy <= y + lineH * 2) ctx.fillText(line, x, cy)
}

function BorderScreen({
  bot,
  index,
  edge,
  slot,
  count,
}: {
  bot: BotRow
  index: number
  edge: Edge
  slot: number
  count: number
}) {
  const color = beamColorFor(bot.id, index)
  const pose = place(edge, slot, count)
  const map = useMemo(() => paintScreen(bot, index, color), [bot, index, color])
  const scan = useRef<Mesh>(null)
  const ghost = useRef<Mesh>(null)
  const reduced = useMemo(() => prefersReducedMotion(), [])

  useEffect(() => () => map.dispose(), [map])

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (scan.current && !reduced) {
      scan.current.position.y = Math.sin(t * 0.7 + index) * 2.5
    }
    if (ghost.current) {
      const mat = ghost.current.material as { opacity: number }
      mat.opacity = reduced ? 0.4 : 0.28 + Math.sin(t * 1.6 + index) * 0.1
    }
  })

  return (
    <group position={[pose.x, 3.55, pose.z]} rotation={[0, pose.rot, 0]} raycast={() => null}>
      <mesh>
        <boxGeometry args={[4.7, 6.7, 0.14]} />
        <meshStandardMaterial color="#07060f" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[0, 0, 0.09]}>
        <planeGeometry args={[4.3, 6.2]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * 2.28, 0, 0.12]}>
          <boxGeometry args={[0.06, 6.4, 0.04]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 3.28, 0.12]}>
        <boxGeometry args={[4.5, 0.06, 0.04]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      {/* Hologram of this tower, standing in front of the screen. */}
      <mesh ref={ghost} position={[0, -0.15, 0.7]}>
        <boxGeometry args={[1.15, 3.5, 0.7]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.55}
          transparent
          opacity={0.38}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, 1.85, 0.7]}>
        <cylinderGeometry args={[0.08, 0.12, 0.7, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.75} toneMapped={false} />
      </mesh>
      <mesh ref={scan} position={[0, 0, 0.85]}>
        <planeGeometry args={[4.1, 0.05]} />
        <meshBasicMaterial color={color} transparent opacity={0.65} toneMapped={false} />
      </mesh>
    </group>
  )
}

/** Huge inward-facing screens on the plaza border, one hologram per live tower. */
export function BorderScreens({ bots }: { bots: BotRow[] }) {
  const list = bots.filter((b) => b.present !== false)
  const shown = list.length ? list : bots
  const counts = countsFor(shown.length)
  let cursor = 0
  const placed: { bot: BotRow; index: number; edge: Edge; slot: number; count: number }[] = []
  EDGES.forEach((edge, ei) => {
    const count = counts[ei]
    for (let slot = 0; slot < count; slot++) {
      const bot = shown[cursor]
      if (!bot) break
      placed.push({ bot, index: cursor, edge, slot, count })
      cursor += 1
    }
  })

  return (
    <group>
      {placed.map((p) => (
        <BorderScreen key={p.bot.id} {...p} />
      ))}
    </group>
  )
}
