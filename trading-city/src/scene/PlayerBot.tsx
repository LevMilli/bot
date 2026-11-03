import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, Vector3, type Group } from 'three'
import {
  clampToBounds,
  resolveObstacles,
  vaultFloorBounds,
  type FloorObstacle,
  type WalkBounds,
} from '../data/bankWalk'

const EYE_H = 1.55
const BODY_H = 1.45
const CAPSULE_R = 0.32
const WALK_SPEED = 5.1
const SPRINT_MUL = 1.6
const ACCEL = 42
const FRICTION = 26
const AIR_CTRL = 0.3
const JUMP_V = 6.0
const GRAVITY = 24
const INTERACT_R = 2.85
const LOOK_SENS = 0.0021
/** A/D turn — A turns character left (camera swings right). */
const TURN_SPEED = 2.35
const TURN_SPRINT = 2.9
/** Over-shoulder follow — reads as a person, not a free camera. */
const CAM_BACK = 2.7
const CAM_UP = 1.9
const CAM_SIDE = 0.35
const CAM_LERP = 12
const BOB_AMT = 0.055

export type PlayerBotProps = {
  active: boolean
  hallHalfW: number
  zBack: number
  zFront: number
  obstacles?: FloorObstacle[]
  /** World positions of teller rope mouths (interact points). */
  tellerMouths: { x: number; z: number; id: string | null; index: number }[]
  onInteract: (id: string, index: number) => void
  onHintChange?: (hint: string) => void
}

/**
 * Grounded third-person player for the vault (and later plaza / floors).
 * W/S walk · A/D turn (A=left / cam right) · mouse look · Space jump · E talk.
 */
export function PlayerBot({
  active,
  hallHalfW,
  zBack,
  zFront,
  obstacles = [],
  tellerMouths,
  onInteract,
  onHintChange,
}: PlayerBotProps) {
  const { camera, gl } = useThree()
  const body = useRef<Group>(null)
  const pos = useRef(new Vector3(0, 0, Math.min(zFront - 2.8, 5)))
  const vel = useRef(new Vector3())
  const yaw = useRef(Math.PI)
  const pitch = useRef(0.1)
  const grounded = useRef(true)
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const locked = useRef(false)
  const dragging = useRef(false)
  const hintRef = useRef('')
  const bobPhase = useRef(0)
  const camPos = useRef(new Vector3(0, 2, 6))
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
    pitch.current = 0.1
    grounded.current = true
    bobPhase.current = 0
    const backX = Math.sin(yaw.current) * -CAM_BACK
    const backZ = Math.cos(yaw.current) * -CAM_BACK
    camPos.current.set(pos.current.x + backX, CAM_UP, pos.current.z + backZ)
    camera.position.copy(camPos.current)
  }, [active, zFront, onHintChange, camera])

  useEffect(() => {
    if (!active) return
    const el = gl.domElement

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON') return
      const k = e.key.toLowerCase()
      keys.current[k] = true
      if (
        k === ' ' ||
        k === 'spacebar' ||
        k === 'arrowup' ||
        k === 'arrowdown' ||
        k === 'arrowleft' ||
        k === 'arrowright' ||
        k === 'a' ||
        k === 'd'
      ) {
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
      if (!document.pointerLockElement) el.requestPointerLock()
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
      pitch.current = MathUtils.clamp(pitch.current - e.movementY * LOOK_SENS, -0.35, 0.55)
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
    const dt = Math.min(0.033, rawDt)
    const k = keys.current

    // A / ← = turn left (yaw+); D / → = turn right (yaw−).
    // Turning left swings the follow-cam to the character's right.
    const turn =
      (k.a || k.arrowleft ? 1 : 0) - (k.d || k.arrowright ? 1 : 0)
    if (turn !== 0) {
      const rate = (k.shift ? TURN_SPRINT : TURN_SPEED) * turn
      yaw.current += rate * dt
    }

    const forward = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0)
    const sin = Math.sin(yaw.current)
    const cos = Math.cos(yaw.current)
    // Walk only along facing — A/D turn the body instead of strafing.
    const wishX = forward * sin
    const wishZ = forward * cos
    const maxSpeed = WALK_SPEED * (k.shift ? SPRINT_MUL : 1)
    const wishSpeed = forward ? maxSpeed : 0

    const control = grounded.current ? 1 : AIR_CTRL
    if (wishSpeed > 0) {
      vel.current.x += wishX * ACCEL * control * dt
      vel.current.z += wishZ * ACCEL * control * dt
      const spd = Math.hypot(vel.current.x, vel.current.z)
      if (spd > maxSpeed) {
        vel.current.x = (vel.current.x / spd) * maxSpeed
        vel.current.z = (vel.current.z / spd) * maxSpeed
      }
    } else if (grounded.current) {
      const spd = Math.hypot(vel.current.x, vel.current.z)
      if (spd > 0.01) {
        const drop = Math.min(spd, FRICTION * dt)
        vel.current.x *= (spd - drop) / spd
        vel.current.z *= (spd - drop) / spd
      } else {
        vel.current.x = 0
        vel.current.z = 0
      }
    }

    if ((k[' '] || k.spacebar) && grounded.current) {
      vel.current.y = JUMP_V
      grounded.current = false
    }
    vel.current.y -= GRAVITY * dt

    let nx = pos.current.x + vel.current.x * dt
    let nz = pos.current.z
    let hit = resolveObstacles(nx, nz, CAPSULE_R, obstacles)
    nx = hit.x
    nz = hit.z
    const bx = clampToBounds(nx, nz, bounds)
    if (bx.x !== nx) vel.current.x = 0
    nx = bx.x

    nz = pos.current.z + vel.current.z * dt
    hit = resolveObstacles(nx, nz, CAPSULE_R, obstacles)
    nx = hit.x
    nz = hit.z
    const bz = clampToBounds(nx, nz, bounds)
    if (bz.z !== nz) vel.current.z = 0
    nx = bz.x
    nz = bz.z

    pos.current.x = nx
    pos.current.z = nz
    pos.current.y += vel.current.y * dt
    if (pos.current.y <= 0) {
      pos.current.y = 0
      vel.current.y = 0
      grounded.current = true
    }

    const groundSpeed = Math.hypot(vel.current.x, vel.current.z)
    if (grounded.current && groundSpeed > 0.35) {
      bobPhase.current += dt * (9.2 + groundSpeed)
    } else {
      bobPhase.current = MathUtils.damp(bobPhase.current, 0, 10, dt)
    }
    const bob =
      grounded.current ? Math.sin(bobPhase.current) * BOB_AMT * Math.min(1, groundSpeed / 2.8) : 0
    const lean = turn !== 0 ? -turn * 0.08 : 0

    if (body.current) {
      body.current.position.set(pos.current.x, pos.current.y + Math.abs(bob) * 0.15, pos.current.z)
      body.current.rotation.y = yaw.current
      body.current.rotation.z = MathUtils.damp(body.current.rotation.z, lean, 10, dt)
    }

    // Follow cam: behind + slight right offset; turning left → cam arcs right.
    const backX = Math.sin(yaw.current) * -CAM_BACK + Math.cos(yaw.current) * CAM_SIDE
    const backZ = Math.cos(yaw.current) * -CAM_BACK - Math.sin(yaw.current) * CAM_SIDE
    const wantCamX = pos.current.x + backX
    const wantCamY = pos.current.y + CAM_UP + bob + pitch.current * 0.55
    const wantCamZ = pos.current.z + backZ
    camPos.current.x = MathUtils.damp(camPos.current.x, wantCamX, CAM_LERP, dt)
    camPos.current.y = MathUtils.damp(camPos.current.y, wantCamY, CAM_LERP, dt)
    camPos.current.z = MathUtils.damp(camPos.current.z, wantCamZ, CAM_LERP, dt)
    camera.position.copy(camPos.current)
    const lookX = pos.current.x + Math.sin(yaw.current) * 4.2
    const lookY = pos.current.y + EYE_H + pitch.current * 2.2
    const lookZ = pos.current.z + Math.cos(yaw.current) * 4.2
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
        ? 'W/S walk · A/D turn · Space jump · Shift sprint · Esc unlock'
        : 'Click to look · W/S walk · A/D turn · Space jump · E talk'
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  if (!active) return null

  return (
    <group ref={body} position={[0, 0, Math.min(zFront - 2.8, 5)]}>
      <mesh position={[0, BODY_H * 0.42, 0]} castShadow>
        <capsuleGeometry args={[CAPSULE_R * 0.75, BODY_H * 0.5, 5, 10]} />
        <meshStandardMaterial
          color="#5ad4e8"
          roughness={0.4}
          metalness={0.35}
          emissive="#1a8098"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[0, BODY_H * 0.92, 0]} castShadow>
        <sphereGeometry args={[0.2, 12, 12]} />
        <meshStandardMaterial color="#e8fdff" roughness={0.25} metalness={0.45} />
      </mesh>
      <mesh position={[0, BODY_H * 0.95, 0.16]}>
        <boxGeometry args={[0.14, 0.04, 0.04]} />
        <meshStandardMaterial color="#061018" metalness={0.7} roughness={0.2} />
      </mesh>
      {/* Simple feet so walk reads */}
      {([-0.12, 0.12] as const).map((x) => (
        <mesh key={x} position={[x, 0.06, 0.06]}>
          <boxGeometry args={[0.1, 0.08, 0.18]} />
          <meshStandardMaterial color="#0a1820" roughness={0.6} metalness={0.3} />
        </mesh>
      ))}
    </group>
  )
}
