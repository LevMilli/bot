import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, Vector3 } from 'three'
import { clampBankWalk } from '../data/bankWalk'

const EYE_H = 1.55
const MOVE_SPEED = 4.2
const SPRINT = 1.55
const JUMP_V = 5.2
const GRAVITY = 16
const INTERACT_R = 2.35

export type PlayerBotProps = {
  active: boolean
  aisleHalf: number
  laneHalf: number
  zBack: number
  zFront: number
  /** World positions of teller rope mouths (interact points). */
  tellerMouths: { x: number; z: number; id: string | null; index: number }[]
  onInteract: (id: string, index: number) => void
  onHintChange?: (hint: string) => void
}

/**
 * First-person guest bot in the vault — WASD walk, Space jump, mouse look, E interact.
 * Camera is the bot POV (no self-mesh so the view stays clean).
 */
export function PlayerBot({
  active,
  aisleHalf,
  laneHalf,
  zBack,
  zFront,
  tellerMouths,
  onInteract,
  onHintChange,
}: PlayerBotProps) {
  const { camera, gl } = useThree()
  const pos = useRef(new Vector3(0, 0, zFront - 2.2))
  const yaw = useRef(Math.PI) // face vault (−Z)
  const pitch = useRef(0)
  const velY = useRef(0)
  const grounded = useRef(true)
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const locked = useRef(false)
  const hintRef = useRef('')

  useEffect(() => {
    if (!active) {
      locked.current = false
      if (document.pointerLockElement) document.exitPointerLock()
      hintRef.current = ''
      onHintChange?.('')
      return
    }
    pos.current.set(0, 0, Math.min(zFront - 2.2, 4.5))
    yaw.current = Math.PI
    pitch.current = 0
    velY.current = 0
    grounded.current = true
  }, [active, zFront, onHintChange])

  useEffect(() => {
    if (!active) return
    const el = gl.domElement

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const k = e.key.toLowerCase()
      keys.current[k] = true
      if (k === ' ' || k === 'spacebar') e.preventDefault()
      if (k === 'e') {
        e.preventDefault()
        const n = nearest.current
        if (n?.id) onInteract(n.id, n.index)
      }
    }
    const onKeyUp = (e: KeyboardEvent) => {
      keys.current[e.key.toLowerCase()] = false
    }
    const onClick = () => {
      if (!document.pointerLockElement) el.requestPointerLock()
    }
    const onLockChange = () => {
      locked.current = document.pointerLockElement === el
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!locked.current) return
      yaw.current -= e.movementX * 0.0022
      pitch.current = MathUtils.clamp(pitch.current - e.movementY * 0.002, -1.15, 1.15)
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    el.addEventListener('click', onClick)
    document.addEventListener('pointerlockchange', onLockChange)
    window.addEventListener('mousemove', onMouseMove)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      el.removeEventListener('click', onClick)
      document.removeEventListener('pointerlockchange', onLockChange)
      window.removeEventListener('mousemove', onMouseMove)
      if (document.pointerLockElement === el) document.exitPointerLock()
      keys.current = {}
    }
  }, [active, gl, onInteract])

  useFrame((_, dt) => {
    if (!active) return
    const k = keys.current
    const forward = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0)
    const strafe = (k.d || k.arrowright ? 1 : 0) - (k.a || k.arrowleft ? 1 : 0)
    const speed = MOVE_SPEED * (k.shift ? SPRINT : 1)

    const sin = Math.sin(yaw.current)
    const cos = Math.cos(yaw.current)
    const dx = (strafe * cos + forward * sin) * speed * dt
    const dz = (-strafe * sin + forward * cos) * speed * dt

    // Roomier FPV bounds — aisle + lane mouths, not through desk bodies.
    const next = clampBankWalk(pos.current.x + dx, pos.current.z + dz, {
      aisleHalf: aisleHalf + 0.85,
      laneHalf: laneHalf * 0.35,
      zBack,
      zFront,
    })
    pos.current.x = next.x
    pos.current.z = next.z

    if ((k[' '] || k.spacebar) && grounded.current) {
      velY.current = JUMP_V
      grounded.current = false
    }
    velY.current -= GRAVITY * dt
    pos.current.y += velY.current * dt
    if (pos.current.y <= 0) {
      pos.current.y = 0
      velY.current = 0
      grounded.current = true
    }

    const eyeY = pos.current.y + EYE_H
    camera.position.set(pos.current.x, eyeY, pos.current.z)
    const lookX = pos.current.x + Math.sin(yaw.current) * Math.cos(pitch.current)
    const lookY = eyeY + Math.sin(pitch.current)
    const lookZ = pos.current.z + Math.cos(yaw.current) * Math.cos(pitch.current)
    camera.lookAt(lookX, lookY, lookZ)

    let best: { id: string; index: number; d: number } | null = null
    for (const t of tellerMouths) {
      if (!t.id) continue
      const d = Math.hypot(t.x - pos.current.x, t.z - pos.current.z)
      if (d <= INTERACT_R && (!best || d < best.d)) best = { id: t.id, index: t.index, d }
    }
    nearest.current = best ? { id: best.id, index: best.index } : null
    const hint = best
      ? 'E · talk to teller'
      : locked.current
        ? 'WASD walk · Space jump · Shift sprint · Esc unlock look'
        : 'Click canvas to look · WASD walk · Space jump · E talk'
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  return null
}
