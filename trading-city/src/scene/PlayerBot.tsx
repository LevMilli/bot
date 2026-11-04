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

const INTERACT_R = 2.95

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
 * Vault third-person player — thin wrapper over shared groundedWalk physics
 * (same locomotion the office / wing walker should use).
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
  const leftFoot = useRef<Group>(null)
  const rightFoot = useRef<Group>(null)
  const state = useRef<GroundedState>(createGroundedState(0, Math.min(zFront - 2.8, 5), Math.PI))
  const keys = useRef<Record<string, boolean>>({})
  const nearest = useRef<{ id: string; index: number } | null>(null)
  const nearIdx = useRef<number | null>(null)
  const locked = useRef(false)
  const dragging = useRef(false)
  const hintRef = useRef('')
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
    resetGroundedState(state.current, 0, Math.min(zFront - 2.8, 5), Math.PI)
    nearIdx.current = null
    onNearChange?.(null)
    camera.position.copy(state.current.camPos)
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
    const s = state.current
    const pose = stepGroundedWalk(s, {
      dt: rawDt,
      keys: keys.current,
      obstacles,
      clampXZ,
      camClamp,
    })

    if (body.current) {
      body.current.position.set(s.pos.x, s.pos.y + Math.abs(pose.bob) * 0.18, s.pos.z)
      body.current.rotation.y = s.yaw
      body.current.rotation.z = MathUtils.damp(body.current.rotation.z, pose.lean, 10, Math.min(0.033, rawDt))
      body.current.rotation.x = MathUtils.damp(body.current.rotation.x, pose.pitchLean, 8, Math.min(0.033, rawDt))
    }
    if (leftFoot.current) {
      leftFoot.current.position.set(-0.12, 0.06 + pose.leftLift, 0.06 + pose.step * 0.12)
      leftFoot.current.rotation.x = pose.step * 0.35
    }
    if (rightFoot.current) {
      rightFoot.current.position.set(0.12, 0.06 + pose.rightLift, 0.06 - pose.step * 0.12)
      rightFoot.current.rotation.x = -pose.step * 0.35
    }

    camera.position.copy(s.camPos)
    camera.lookAt(
      s.pos.x + Math.sin(s.yaw) * 4.2,
      s.pos.y + GROUNDED.eyeH + s.pitch * 2.2,
      s.pos.z + Math.cos(s.yaw) * 4.2,
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
    <group ref={body} position={[0, 0, Math.min(zFront - 2.8, 5)]}>
      <mesh position={[0, GROUNDED.bodyH * 0.42, 0]} castShadow>
        <capsuleGeometry args={[GROUNDED.capsuleR * 0.75, GROUNDED.bodyH * 0.5, 5, 10]} />
        <meshStandardMaterial
          color="#5ad4e8"
          roughness={0.4}
          metalness={0.35}
          emissive="#1a8098"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[0, GROUNDED.bodyH * 0.92, 0]} castShadow>
        <sphereGeometry args={[0.2, 12, 12]} />
        <meshStandardMaterial color="#e8fdff" roughness={0.25} metalness={0.45} />
      </mesh>
      <mesh position={[0, GROUNDED.bodyH * 0.95, 0.16]}>
        <boxGeometry args={[0.14, 0.04, 0.04]} />
        <meshStandardMaterial color="#061018" metalness={0.7} roughness={0.2} />
      </mesh>
      <group ref={leftFoot} position={[-0.12, 0.06, 0.06]}>
        <mesh>
          <boxGeometry args={[0.1, 0.08, 0.18]} />
          <meshStandardMaterial color="#0a1820" roughness={0.6} metalness={0.3} />
        </mesh>
      </group>
      <group ref={rightFoot} position={[0.12, 0.06, 0.06]}>
        <mesh>
          <boxGeometry args={[0.1, 0.08, 0.18]} />
          <meshStandardMaterial color="#0a1820" roughness={0.6} metalness={0.3} />
        </mesh>
      </group>
    </group>
  )
}
