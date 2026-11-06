import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import type { BotRow, Desk } from '../types'
import { money } from '../data/format'

type Point = { x: number; y: number }

function seriesFrom(bot: BotRow, desk?: Desk): Point[] {
  const hist = bot.history || []
  if (hist.length) {
    let run = 0
    return hist.map((row, i) => {
      run += Number(row.pnl || 0)
      return { x: i, y: run }
    })
  }
  const curve = desk?.curve || desk?.equity || []
  if (curve.length) {
    return curve.map((p, i) => ({ x: i, y: Number(p.v || 0) }))
  }
  if (typeof bot.today === 'number') {
    return [
      { x: 0, y: 0 },
      { x: 1, y: bot.today },
    ]
  }
  return []
}

function paintWallChart(
  label: string,
  points: Point[],
  subtitle: string,
): THREE.CanvasTexture {
  const w = 768
  const h = 512
  const scale = 3
  const canvas = document.createElement('canvas')
  canvas.width = w * scale
  canvas.height = h * scale
  const ctx = canvas.getContext('2d')!
  ctx.scale(scale, scale)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'

  ctx.fillStyle = '#030612'
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = 'rgba(45,226,230,0.55)'
  ctx.lineWidth = 4
  ctx.strokeRect(8, 8, w - 16, h - 16)

  // subtle grid — higher contrast so direction reads from the chair
  ctx.strokeStyle = 'rgba(26,156,255,0.28)'
  ctx.lineWidth = 1.5
  for (let i = 1; i < 6; i++) {
    const y = 64 + ((h - 120) * i) / 6
    ctx.beginPath()
    ctx.moveTo(40, y)
    ctx.lineTo(w - 40, y)
    ctx.stroke()
  }

  ctx.fillStyle = '#9aa3c7'
  ctx.font = '22px monospace'
  ctx.fillText(label.slice(0, 36), 36, 44)

  const last = points.length ? points[points.length - 1].y : null
  const prev = points.length > 1 ? points[points.length - 2].y : 0
  const delta = last == null ? 0 : last - prev
  const up = delta >= 0
  const stroke = points.length === 0 ? '#9aa3c7' : up ? '#39ff14' : '#ff2a6d'

  ctx.fillStyle = stroke
  ctx.font = 'bold 28px monospace'
  const deltaLabel =
    last == null ? 'NO DATA' : `${up ? '▲' : '▼'} ${money(last, true)}`
  ctx.fillText(deltaLabel, w - 36 - ctx.measureText(deltaLabel).width, 44)

  ctx.fillStyle = '#7a849f'
  ctx.font = '18px monospace'
  ctx.fillText(subtitle.slice(0, 48), 36, h - 28)

  const plotX = 48
  const plotY = 72
  const plotW = w - 96
  const plotH = h - 140

  ctx.fillStyle = 'rgba(20,40,80,0.35)'
  ctx.fillRect(plotX, plotY, plotW, plotH)

  if (!points.length) {
    ctx.fillStyle = '#9aa3c7'
    ctx.font = '24px monospace'
    ctx.fillText('Waiting on live equity / history', plotX + 48, plotY + plotH / 2)
  } else {
    const ys = points.map((p) => p.y)
    const minY = Math.min(...ys, 0)
    const span = Math.max(...ys, 0) - minY || 1
    const zeroY = plotY + plotH - ((0 - minY) / span) * plotH

    ctx.strokeStyle = 'rgba(249,200,14,0.45)'
    ctx.beginPath()
    ctx.moveTo(plotX, zeroY)
    ctx.lineTo(plotX + plotW, zeroY)
    ctx.stroke()

    // fill under curve
    ctx.beginPath()
    points.forEach((p, i) => {
      const x = plotX + (i / Math.max(points.length - 1, 1)) * plotW
      const y = plotY + plotH - ((p.y - minY) / span) * plotH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    const lastX = plotX + plotW
    const lastY =
      plotY + plotH - ((points[points.length - 1].y - minY) / span) * plotH
    ctx.lineTo(lastX, plotY + plotH)
    ctx.lineTo(plotX, plotY + plotH)
    ctx.closePath()
    ctx.fillStyle = up ? 'rgba(57,255,20,0.2)' : 'rgba(255,42,109,0.2)'
    ctx.fill()

    ctx.strokeStyle = stroke
    ctx.lineWidth = 5.5
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.beginPath()
    points.forEach((p, i) => {
      const x = plotX + (i / Math.max(points.length - 1, 1)) * plotW
      const y = plotY + plotH - ((p.y - minY) / span) * plotH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // tip dot
    ctx.beginPath()
    ctx.arc(lastX, lastY, 8, 0, Math.PI * 2)
    ctx.fillStyle = stroke
    ctx.fill()
  }

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 16
  tex.minFilter = THREE.LinearFilter
  tex.magFilter = THREE.LinearFilter
  tex.generateMipmaps = false
  tex.needsUpdate = true
  return tex
}

/** Large live equity panel mounted on an office side wall. */
export function WallStockChart({
  bot,
  desk,
  side,
}: {
  bot: BotRow
  desk?: Desk
  side: 'left' | 'right'
}) {
  const points = useMemo(() => seriesFrom(bot, desk), [bot, desk])
  const map = useMemo(() => {
    const label =
      side === 'left'
        ? `${bot.name} · LIVE`
        : `DESK · ${bot.id}`
    const subtitle =
      side === 'left'
        ? `today ${money(bot.today, true)} · open ${bot.open_count ?? 0}`
        : `desk today ${money(desk?.today, true)} · ${desk?.status_line || 'paper desk'}`
    const series =
      side === 'right' && (desk?.curve?.length || desk?.equity?.length)
        ? (desk?.curve || desk?.equity || []).map((p, i) => ({
            x: i,
            y: Number(p.v || 0),
          }))
        : points
    return paintWallChart(label, series, subtitle)
  }, [bot, desk, points, side])

  useEffect(() => () => map.dispose(), [map])

  // Mount on the side walls, forward of the desk so the OTS camera catches them.
  const x = side === 'left' ? -3.55 : 3.55
  const rotY = side === 'left' ? Math.PI / 2 + 0.18 : -Math.PI / 2 - 0.18

  return (
    <group position={[x, 1.95, 0.15]} rotation={[0, rotY, 0]}>
      <mesh position={[0, 0, 0.04]}>
        <boxGeometry args={[2.85, 1.75, 0.06]} />
        <meshStandardMaterial color="#0a101c" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[0, 0, 0.08]}>
        <planeGeometry args={[2.65, 1.55]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.92, 0.09]}>
        <boxGeometry args={[2.75, 0.035, 0.03]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.92, 0.09]}>
        <boxGeometry args={[2.75, 0.035, 0.03]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}
