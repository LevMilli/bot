import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, Vector3, type Group } from 'three'
import { vaultFloorBounds, type WalkBounds } from '../data/bankWalk'

const EYE_H = 1.62
const BODY_H = 1.35
const CAPSULE_R = 0.28
const WALK_SPEED = 5.4
const SPRINT_MUL = 1.65
const ACCEL = 28
const FRICTION = 14
const AIR_CTRL = 0.35
const JUMP_V = 6.2
const GRAVITY = 22
const INTERACT_R = 2.5
const LOOK_SENS = 0.0024

export type PlayerBotProps = {
  active: boolean
  hallHalfW: number
  zBack: number
  zFront: number
  /** World positions of teller rope mouths (interact points). */
  tellerMouths: { x: number; z: number; id: string | null; index: number }[]
  onInteract: (id: string, index: number) => void
  onHintChange?: (hint: string) => void
}

/**
 * Grounded player controller for the vault (and later plaza / floors).
 * Smooth accel/friction, jump, free floor walk, mouse look, E interact.
 * Simple capsule body — graphics are intentionally minimal.
 */
export function PlayerBot({
  active,
  hallHalfW,
  zBack,
  zFront,
  tellerMouths,
  onInteract,
  onHintChange,
}: PlayerBotProps) {
  const { camera, gl } = useThree()
  const body = useRef<Group>(null)
  const pos = useRef(new Vector3(0, 0, Math.min(zFront - 2.8, 5)))
  const vel = useRef(new Vector3())
  const yaw = useRef(Math.PI)
  const pitch = useRef(-0.08)
  const grounded = useRef(true)
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const locked = useRef(false)
  const dragging = useRef(false)
  const hintRef = useRef('')
  const bounds = useMemo<WalkBounds>(
    () => vaultFloorBounds(hallHalfW, zBack, zFront, CAPSULE_R),
    [hallHalfW, zBack, zFront],
  )

  useEffect(() => {
    if (!active) {
      locked.current = false
      dragging.current = false
      if (document.pointerLockElement) document.exitPointerLock()
      hintRef.current = ''
      onHintChange?.('')
      return
    }
    pos.current.set(0, 0, Math.min(zFront - 2.8, 5))
    vel.current.set(0, 0, 0)
    yaw.current = Math.PI
    pitch.current = -0.08
    grounded.current = true
  }, [active, zFront, onHintChange])

  useEffect(() => {
    if (!active) return
    const el = gl.domElement

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON') return
      const k = e.key.toLowerCase()
      keys.current[k] = true
      if (k === ' ' || k === 'spacebar' || k === 'arrowup' || k === 'arrowdown' || k === 'arrowleft' || k === 'arrowright') {
        e.preventDefault()
      }
      if (k === 'e') {
        e.preventDefault()
        const n = nearest.current
        if (n?.id) onInteract(n.id, n.index)
      }
    }
    const onKeyUp = (e: KeyboardEvent) => {
      keys.current[e.key.toLowerCase()] = false
    }
    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      if (!document.pointerLockElement) {
        el.requestPointerLock()
      }
      dragging.current = true
    }
    const onPointerUp = () => {
      dragging.current = false
    }
    const onLockChange = () => {
      locked.current = document.pointerLockElement === el
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!locked.current && !dragging.current) return
      yaw.current -= e.movementX * LOOK_SENS
      pitch.current = MathUtils.clamp(pitch.current - e.movementY * LOOK_SENS, -1.2, 1.2)
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    el.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointerup', onPointerUp)
    document.addEventListener('pointerlockchange', onLockChange)
    window.addEventListener('mousemove', onMouseMove)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      el.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointerup', onPointerUp)
      document.removeEventListener('pointerlockchange', onLockChange)
      window.removeEventListener('mousemove', onMouseMove)
      if (document.pointerLockElement === el) document.exitPointerLock()
      keys.current = {}
    }
  }, [active, gl, onInteract])

  useFrame((_, rawDt) => {
    if (!active) return
    const dt = Math.min(0.05, rawDt)
    const k = keys.current
    const forward = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0)
    const strafe = (k.d || k.arrowright ? 1 : 0) - (k.a || k.arrowleft ? 1 : 0)
    const len = Math.hypot(forward, strafe) || 1
    const fx = forward / len
    const sx = strafe / len

    const sin = Math.sin(yaw.current)
    const cos = Math.cos(yaw.current)
    const wishX = sx * cos + fx * sin
    const wishZ = -sx * sin + fx * cos
    const maxSpeed = WALK_SPEED * (k.shift ? SPRINT_MUL : 1)
    const wishSpeed = (forward || strafe ? 1 : 0) * maxSpeed

    const control = grounded.current ? 1 : AIR_CTRL
    const accel = ACCEL * control
    const targetVx = wishX * wishSpeed
    const targetVz = wishZ * wishSpeed

    if (wishSpeed > 0) {
      vel.current.x = MathUtils.damp(vel.current.x, targetVx, accel, dt)
      vel.current.z = MathUtils.damp(vel.current.z, targetVz, accel, dt)
    } else if (grounded.current) {
      vel.current.x = MathUtils.damp(vel.current.x, 0, FRICTION, dt)
      vel.current.z = MathUtils.damp(vel.current.z, 0, FRICTION, dt)
      if (Math.hypot(vel.current.x, vel.current.z) < 0.02) {
        vel.current.x = 0
        vel.current.z = 0
      }
    }

    if ((k[' '] || k.spacebar) && grounded.current) {
      vel.current.y = JUMP_V
      grounded.current = false
    }

    vel.current.y -= GRAVITY * dt

    // Separate axis resolve so walls don't stick.
    let nx = pos.current.x + vel.current.x * dt
    let nz = pos.current.z + vel.current.z * dt
    const clampedX = Math.min(bounds.maxX, Math.max(bounds.minX, nx))
    if (clampedX !== nx) vel.current.x = 0
    nx = clampedX
    const clampedZ = Math.min(bounds.maxZ, Math.max(bounds.minZ, nz))
    if (clampedZ !== nz) vel.current.z = 0
    nz = clampedZ

    pos.current.x = nx
    pos.current.z = nz
    pos.current.y += vel.current.y * dt
    if (pos.current.y <= 0) {
      pos.current.y = 0
      vel.current.y = 0
      grounded.current = true
    }

    const eyeY = pos.current.y + EYE_H
    camera.position.set(pos.current.x, eyeY, pos.current.z)
    const lookX = pos.current.x + Math.sin(yaw.current) * Math.cos(pitch.current)
    const lookY = eyeY + Math.sin(pitch.current)
    const lookZ = pos.current.z + Math.cos(yaw.current) * Math.cos(pitch.current)
    camera.lookAt(lookX, lookY, lookZ)

    if (body.current) {
      body.current.position.set(pos.current.x, pos.current.y, pos.current.z)
      body.current.rotation.y = yaw.current
    }

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
        ? 'WASD / arrows walk · Space jump · Shift sprint · Esc unlock look'
        : 'Click to look · WASD / arrows walk · Space jump · E talk'
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  if (!active) return null

  return (
    <group ref={body} position={[0, 0, Math.min(zFront - 2.8, 5)]}>
      {/* Minimal capsule body — intentional low-detail stand-in for future tower walk. */}
      <mesh position={[0, BODY_H * 0.45, 0]} castShadow>
        <capsuleGeometry args={[CAPSULE_R * 0.85, BODY_H * 0.55, 4, 8]} />
        <meshStandardMaterial color="#7ef9ff" roughness={0.45} metalness={0.25} transparent opacity={0.35} />
      </mesh>
      <mesh position={[0, BODY_H * 0.95, 0]}>
        <sphereGeometry args={[0.18, 10, 10]} />
        <meshStandardMaterial color="#d7fbff" roughness={0.3} metalness={0.4} transparent opacity={0.4} />
      </mesh>
    </group>
  )
}
