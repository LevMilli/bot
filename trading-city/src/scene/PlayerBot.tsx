import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, type Group } from 'three'
import { vaultFloorBounds, type FloorObstacle } from '../data/bankWalk'
import {
  GROUNDED,
  aabbClamp,
  applyLookDelta,
  createGroundedState,
  defaultWalkHint,
  queueJump,
  resetGroundedState,
  stepGroundedWalk,
  type GroundedState,
} from '../data/groundedWalk'
import { PlayerHeroFigure, type PlayerHeroMotion } from './PlayerHeroFigure'

const INTERACT_R = 2.95
/** Farther over-shoulder so the taller industrial hero reads cleanly. */
const HERO_CAM_BACK = 3.45
const HERO_CAM_UP = 2.2
const HERO_CAM_SIDE = 0.48
const HERO_EYE = 1.85
/** Spawn clear of the TrustSeal Html at z≈4.35. */
const SPAWN_Z = 6.1

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
  /** Fires when the nearest interactable teller changes. */
  onNearChange?: (index: number | null) => void
}

/**
 * Vault third-person player — shared groundedWalk physics + hero industrial mesh.
 * Tellers stay on CityBotFigure; this is the guest VIP body only.
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
  onNearChange,
}: PlayerBotProps) {
  const { camera, gl } = useThree()
  const body = useRef<Group>(null)
  const state = useRef<GroundedState>(createGroundedState(0, Math.min(zFront - 2.4, SPAWN_Z), Math.PI))
  const motion = useRef<PlayerHeroMotion>({
    step: 0,
    bobAmp: 0,
    groundSpeed: 0,
    grounded: true,
    jumping: false,
    sprinting: false,
    turn: 0,
  })
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const nearIdx = useRef<number | null>(null)
  const locked = useRef(false)
  const dragging = useRef(false)
  const hintRef = useRef('')
  const landPunch = useRef(0)
  const bounds = useMemo(
    () => vaultFloorBounds(hallHalfW, zBack, zFront, GROUNDED.capsuleR),
    [hallHalfW, zBack, zFront],
  )
  const clampXZ = useMemo(() => aabbClamp(bounds), [bounds])
  const camClamp = useMemo(
    () => ({
      minX: -hallHalfW + GROUNDED.camWallPad,
      maxX: hallHalfW - GROUNDED.camWallPad,
      minZ: zBack + GROUNDED.camWallPad + 0.8,
      maxZ: zFront - GROUNDED.camWallPad,
    }),
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
    resetGroundedState(state.current, 0, Math.min(zFront - 2.4, SPAWN_Z), Math.PI)
    // Seed a wider hero camera behind the spawn.
    const s = state.current
    const backX = Math.sin(s.yaw) * -HERO_CAM_BACK + Math.cos(s.yaw) * HERO_CAM_SIDE
    const backZ = Math.cos(s.yaw) * -HERO_CAM_BACK - Math.sin(s.yaw) * HERO_CAM_SIDE
    s.camPos.set(s.pos.x + backX, HERO_CAM_UP, s.pos.z + backZ)
    nearIdx.current = null
    landPunch.current = 0
    onNearChange?.(null)
    camera.position.copy(s.camPos)
  }, [active, zFront, onHintChange, onNearChange, camera])

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
      if (k === ' ' || k === 'spacebar') queueJump(state.current)
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
      applyLookDelta(state.current, e.movementX, e.movementY)
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
    const s = state.current
    const wasAir = !s.grounded
    const k = keys.current
    const pose = stepGroundedWalk(s, {
      dt: rawDt,
      keys: k,
      obstacles,
      clampXZ,
      camClamp,
    })

    // Override follow cam for the taller hero silhouette.
    const backX = Math.sin(s.yaw) * -HERO_CAM_BACK + Math.cos(s.yaw) * HERO_CAM_SIDE
    const backZ = Math.cos(s.yaw) * -HERO_CAM_BACK - Math.sin(s.yaw) * HERO_CAM_SIDE
    let wantCamX = s.pos.x + backX
    const wantCamY = s.pos.y + HERO_CAM_UP + pose.bob + s.pitch * 0.55
    let wantCamZ = s.pos.z + backZ
    wantCamX = MathUtils.clamp(wantCamX, camClamp.minX, camClamp.maxX)
    wantCamZ = MathUtils.clamp(wantCamZ, camClamp.minZ, camClamp.maxZ)
    s.camPos.x = MathUtils.damp(s.camPos.x, wantCamX, GROUNDED.camLerp, dt)
    s.camPos.y = MathUtils.damp(s.camPos.y, wantCamY, GROUNDED.camLerp, dt)
    s.camPos.z = MathUtils.damp(s.camPos.z, wantCamZ, GROUNDED.camLerp, dt)

    if (wasAir && s.grounded) landPunch.current = 1
    landPunch.current = MathUtils.damp(landPunch.current, 0, 8, dt)

    motion.current.step = pose.step
    motion.current.bobAmp = pose.bobAmp
    motion.current.groundSpeed = pose.groundSpeed
    motion.current.grounded = s.grounded
    motion.current.jumping = !s.grounded
    motion.current.sprinting = Boolean(k.shift) && pose.groundSpeed > 1.2
    motion.current.turn = pose.turn

    if (body.current) {
      const punch = landPunch.current * 0.06
      body.current.position.set(
        s.pos.x,
        s.pos.y + Math.abs(pose.bob) * 0.2 - punch,
        s.pos.z,
      )
      body.current.rotation.y = s.yaw
      body.current.rotation.z = MathUtils.damp(body.current.rotation.z, pose.lean, 10, dt)
      body.current.rotation.x = MathUtils.damp(body.current.rotation.x, pose.pitchLean, 8, dt)
    }

    camera.position.copy(s.camPos)
    camera.lookAt(
      s.pos.x + Math.sin(s.yaw) * 4.4,
      s.pos.y + HERO_EYE + s.pitch * 2.2,
      s.pos.z + Math.cos(s.yaw) * 4.4,
    )

    let best: { id: string; index: number; d: number } | null = null
    for (const t of tellerMouths) {
      if (!t.id) continue
      const d = Math.hypot(t.x - s.pos.x, t.z - s.pos.z)
      if (d <= INTERACT_R && (!best || d < best.d)) best = { id: t.id, index: t.index, d }
    }
    nearest.current = best ? { id: best.id, index: best.index } : null
    const nextNear = best ? best.index : null
    if (nextNear !== nearIdx.current) {
      nearIdx.current = nextNear
      onNearChange?.(nextNear)
    }
    const hint = defaultWalkHint(locked.current, best ? 'E · talk to teller' : null)
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  if (!active) return null

  return (
    <group ref={body} position={[0, 0, Math.min(zFront - 2.4, SPAWN_Z)]}>
      <PlayerHeroFigure motion={motion} />
    </group>
  )
}
