import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, Vector3, type Group } from 'three'
import { clampToBounds, resolveObstacles, type FloorObstacle, type WalkBounds } from '../data/bankWalk'
import {
  PLAYER_R,
  clampWingWalk,
  roomAtPosition,
  spawnBehindBot,
  wingDeskObstacles,
  wingOuterBounds,
} from '../data/wingWalk'

const EYE_FOLLOW = 1.72
const CAM_BACK = 2.35
const CAM_UP = 1.78
const CAM_LERP = 11
const WALK_SPEED = 4.6
const SPRINT_MUL = 1.5
const ACCEL = 36
const FRICTION = 20
const LOOK_SENS = 0.0022
const BOB_AMT = 0.04

type Props = {
  active: boolean
  /** Tower / teller bot we entered from — spawn behind this desk bot (once per entry). */
  focusBotId: string
  onEnterRoom?: (botId: string) => void
  onHintChange?: (hint: string) => void
}

/**
 * Free walk for the trading wing. Third-person body, WASD + mouse look (turn full 360°).
 * Spawn sits behind the tower bot. Walking into another suite swaps live desk LOD without re-spawn.
 * Bounds/obstacles live in wingWalk so a shared physics agent can replace this body later.
 */
export function WingWalker({ active, focusBotId, onEnterRoom, onHintChange }: Props) {
  const { camera, gl } = useThree()
  const body = useRef<Group>(null)
  const pos = useRef(new Vector3())
  const vel = useRef(new Vector3())
  const yaw = useRef(0)
  const pitch = useRef(0.1)
  const keys = useRef<Record<string, boolean>>({})
  const dragging = useRef(false)
  const locked = useRef(false)
  const bob = useRef(0)
  const camPos = useRef(new Vector3())
  const lastRoom = useRef<string | null>(null)
  const spawnKey = useRef('')

  const obstacles = useMemo<FloorObstacle[]>(() => wingDeskObstacles(), [])
  const outer = useMemo<WalkBounds>(() => wingOuterBounds(PLAYER_R), [])

  const respawn = (botId: string) => {
    const spawn = spawnBehindBot(botId)
    pos.current.set(spawn.position[0], 0, spawn.position[2])
    vel.current.set(0, 0, 0)
    yaw.current = spawn.yaw
    pitch.current = 0.08
    bob.current = 0
    const backX = Math.sin(yaw.current) * -CAM_BACK
    const backZ = Math.cos(yaw.current) * -CAM_BACK
    camPos.current.set(pos.current.x + backX, CAM_UP, pos.current.z + backZ)
    camera.position.copy(camPos.current)
    lastRoom.current = spawn.room?.botId ?? null
    spawnKey.current = botId
  }

  useEffect(() => {
    if (!active) {
      locked.current = false
      dragging.current = false
      if (document.pointerLockElement) document.exitPointerLock()
      onHintChange?.('')
      return
    }
    respawn(focusBotId)
    onHintChange?.('WASD walk · drag/look · Shift sprint · click canvas to lock mouse')
  }, [active, focusBotId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!active) return
    const el = gl.domElement

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const k = e.key.toLowerCase()
      keys.current[k] = true
      if ([' ', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) e.preventDefault()
    }
    const onKeyUp = (e: KeyboardEvent) => {
      keys.current[e.key.toLowerCase()] = false
    }
    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      dragging.current = true
      try {
        el.requestPointerLock()
      } catch {
        /* ignore */
      }
    }
    const onPointerUp = () => {
      dragging.current = false
    }
    const onMove = (e: MouseEvent) => {
      if (!dragging.current && !locked.current) return
      yaw.current -= e.movementX * LOOK_SENS
      pitch.current = MathUtils.clamp(pitch.current - e.movementY * LOOK_SENS, -0.55, 0.55)
    }
    const onLock = () => {
      locked.current = document.pointerLockElement === el
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    el.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('mousemove', onMove)
    document.addEventListener('pointerlockchange', onLock)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      el.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('mousemove', onMove)
      document.removeEventListener('pointerlockchange', onLock)
    }
  }, [active, gl])

  useFrame((_, dt) => {
    if (!active) return
    const d = Math.min(0.05, dt)
    const k = keys.current
    const forward = (k.w || k.arrowup ? 1 : 0) + (k.s || k.arrowdown ? -1 : 0)
    const strafe = (k.d || k.arrowright ? 1 : 0) + (k.a || k.arrowleft ? -1 : 0)
    const sprint = k.shift ? SPRINT_MUL : 1
    const speed = WALK_SPEED * sprint

    const wish = new Vector3()
    if (forward || strafe) {
      const fx = Math.sin(yaw.current)
      const fz = Math.cos(yaw.current)
      wish.set(fx * forward + fz * strafe, 0, fz * forward - fx * strafe)
      if (wish.lengthSq() > 1e-6) wish.normalize().multiplyScalar(speed)
    }

    vel.current.x = MathUtils.damp(vel.current.x, wish.x, forward || strafe ? ACCEL / 10 : FRICTION / 8, d)
    vel.current.z = MathUtils.damp(vel.current.z, wish.z, forward || strafe ? ACCEL / 10 : FRICTION / 8, d)

    let nx = pos.current.x + vel.current.x * d
    let nz = pos.current.z + vel.current.z * d
    ;({ x: nx, z: nz } = clampToBounds(nx, nz, outer))
    ;({ x: nx, z: nz } = resolveObstacles(nx, nz, PLAYER_R, obstacles))
    const clamped = clampWingWalk(nx, nz, PLAYER_R)
    nx = clamped.x
    nz = clamped.z
    pos.current.set(nx, 0, nz)

    const moving = Math.hypot(vel.current.x, vel.current.z) > 0.4
    if (moving) bob.current += d * 9 * sprint
    const bobY = moving ? Math.sin(bob.current) * BOB_AMT : 0

    if (body.current) {
      body.current.position.set(nx, bobY, nz)
      body.current.rotation.y = yaw.current
    }

    const room = roomAtPosition(nx, nz)
    if (room && room.botId !== lastRoom.current) {
      lastRoom.current = room.botId
      onEnterRoom?.(room.botId)
    }

    const backX = Math.sin(yaw.current) * -CAM_BACK
    const backZ = Math.cos(yaw.current) * -CAM_BACK
    const want = new Vector3(nx + backX, CAM_UP + bobY * 0.5 + pitch.current * 0.35, nz + backZ)
    camPos.current.lerp(want, 1 - Math.exp(-CAM_LERP * d))
    camera.position.copy(camPos.current)
    const look = new Vector3(nx, EYE_FOLLOW + pitch.current * 0.9, nz)
    camera.lookAt(look)
  })

  if (!active) return null

  return (
    <group ref={body}>
      {/* Soft staff avatar — reads as a person trailing the camera */}
      <mesh position={[0, 0.75, 0]} castShadow={false}>
        <capsuleGeometry args={[0.22, 0.85, 4, 8]} />
        <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.18} roughness={0.45} />
      </mesh>
      <mesh position={[0, 1.45, 0]}>
        <sphereGeometry args={[0.2, 12, 12]} />
        <meshStandardMaterial color="#d8fff8" roughness={0.4} />
      </mesh>
    </group>
  )
}
