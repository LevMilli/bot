import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, type Group } from 'three'
import { vaultFloorBounds, type FloorObstacle } from '../data/bankWalk'
import {
  GROUNDED,
  HERO_TUNE,
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
/** Base over-shoulder — stretches out further when sprinting. */
const HERO_CAM_BACK = 3.35
const HERO_CAM_BACK_SPRINT = 3.95
const HERO_CAM_UP = 2.25
const HERO_CAM_SIDE = 0.52
const HERO_EYE = 1.9
const SPAWN_Z = 6.1

export type PlayerBotProps = {
  active: boolean
  hallHalfW: number
  zBack: number
  zFront: number
  obstacles?: FloorObstacle[]
  tellerMouths: { x: number; z: number; id: string | null; index: number }[]
  onInteract: (id: string, index: number) => void
  onHintChange?: (hint: string) => void
  onNearChange?: (index: number | null) => void
}

/**
 * Vault third-person guest hero — HERO_TUNE locomotion + PlayerHeroFigure v2.
 * Tellers stay on CityBotFigure.
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
    velY: 0,
  })
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const nearIdx = useRef<number | null>(null)
  const locked = useRef(false)
  const dragging = useRef(false)
  const hintRef = useRef('')
  const landPunch = useRef(0)
  const camBack = useRef(HERO_CAM_BACK)
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
    const s = state.current
    const backX = Math.sin(s.yaw) * -HERO_CAM_BACK + Math.cos(s.yaw) * HERO_CAM_SIDE
    const backZ = Math.cos(s.yaw) * -HERO_CAM_BACK - Math.sin(s.yaw) * HERO_CAM_SIDE
    s.camPos.set(s.pos.x + backX, HERO_CAM_UP, s.pos.z + backZ)
    camBack.current = HERO_CAM_BACK
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
      if (k === ' ' || k === 'spacebar') queueJump(state.current, HERO_TUNE.jumpBuffer ?? GROUNDED.jumpBuffer)
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
    const jumpHeld = Boolean(k[' '] || k.spacebar)
    const pose = stepGroundedWalk(s, {
      dt: rawDt,
      keys: k,
      obstacles,
      clampXZ,
      camClamp,
      tune: HERO_TUNE,
      jumpHeld,
    })

    const sprinting = Boolean(k.shift) && pose.groundSpeed > 1.4
    const wantBack = sprinting ? HERO_CAM_BACK_SPRINT : HERO_CAM_BACK
    camBack.current = MathUtils.damp(camBack.current, wantBack, 6, dt)

    const backX = Math.sin(s.yaw) * -camBack.current + Math.cos(s.yaw) * HERO_CAM_SIDE
    const backZ = Math.cos(s.yaw) * -camBack.current - Math.sin(s.yaw) * HERO_CAM_SIDE
    let wantCamX = s.pos.x + backX
    const wantCamY = s.pos.y + HERO_CAM_UP + pose.bob * 1.15 + s.pitch * 0.55 + (sprinting ? 0.08 : 0)
    let wantCamZ = s.pos.z + backZ
    wantCamX = MathUtils.clamp(wantCamX, camClamp.minX, camClamp.maxX)
    wantCamZ = MathUtils.clamp(wantCamZ, camClamp.minZ, camClamp.maxZ)
    // Snappier cam lag when turning so the hero stays framed.
    const camLag = pose.turn !== 0 ? GROUNDED.camLerp + 3 : GROUNDED.camLerp
    s.camPos.x = MathUtils.damp(s.camPos.x, wantCamX, camLag, dt)
    s.camPos.y = MathUtils.damp(s.camPos.y, wantCamY, camLag, dt)
    s.camPos.z = MathUtils.damp(s.camPos.z, wantCamZ, camLag, dt)

    if (wasAir && s.grounded) {
      // Harder land punch from fall speed.
      landPunch.current = Math.min(1.4, 0.55 + Math.abs(pose.velY) * 0.08)
    }
    landPunch.current = MathUtils.damp(landPunch.current, 0, 7, dt)

    motion.current.step = pose.step
    motion.current.bobAmp = pose.bobAmp
    motion.current.groundSpeed = pose.groundSpeed
    motion.current.grounded = s.grounded
    motion.current.jumping = !s.grounded
    motion.current.sprinting = sprinting
    motion.current.turn = pose.turn
    motion.current.velY = pose.velY

    if (body.current) {
      const punch = landPunch.current * 0.09
      body.current.position.set(s.pos.x, s.pos.y + Math.abs(pose.bob) * 0.24 - punch, s.pos.z)
      body.current.rotation.y = s.yaw
      body.current.rotation.z = MathUtils.damp(body.current.rotation.z, pose.lean * 1.15, 12, dt)
      body.current.rotation.x = MathUtils.damp(body.current.rotation.x, pose.pitchLean, 10, dt)
    }

    camera.position.copy(s.camPos)
    camera.lookAt(
      s.pos.x + Math.sin(s.yaw) * 4.6,
      s.pos.y + HERO_EYE + s.pitch * 2.3,
      s.pos.z + Math.cos(s.yaw) * 4.6,
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
