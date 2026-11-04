import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MathUtils, type Group } from 'three'
import { clampToBounds, type FloorObstacle, type WalkBounds } from '../data/bankWalk'
import {
  GROUNDED,
  applyLookDelta,
  createGroundedState,
  defaultWalkHint,
  queueJump,
  resetGroundedState,
  stepGroundedWalk,
  type GroundedState,
} from '../data/groundedWalk'
import {
  PLAYER_R,
  clampWingWalk,
  roomAtPosition,
  spawnBehindBot,
  wingDeskObstacles,
  wingOuterBounds,
} from '../data/wingWalk'

type Props = {
  active: boolean
  /** Tower / teller bot we entered from — spawn behind this desk bot (once per entry). */
  focusBotId: string
  onEnterRoom?: (botId: string) => void
  onHintChange?: (hint: string) => void
}

/**
 * Trading-wing free walk using the same vault teller grounded physics
 * (W/S walk · A/D turn · Space jump · mouse look · Shift sprint).
 * Bounds/obstacles stay in wingWalk; locomotion is shared via groundedWalk.
 */
export function WingWalker({ active, focusBotId, onEnterRoom, onHintChange }: Props) {
  const { camera, gl } = useThree()
  const body = useRef<Group>(null)
  const leftFoot = useRef<Group>(null)
  const rightFoot = useRef<Group>(null)
  const state = useRef<GroundedState>(createGroundedState())
  const keys = useRef<Record<string, boolean>>({})
  const dragging = useRef(false)
  const locked = useRef(false)
  const lastRoom = useRef<string | null>(null)
  const hintRef = useRef('')

  const obstacles = useMemo<FloorObstacle[]>(() => wingDeskObstacles(), [])
  const outer = useMemo<WalkBounds>(() => wingOuterBounds(PLAYER_R), [])

  const clampXZ = useMemo(
    () => (x: number, z: number) => {
      const coarse = clampToBounds(x, z, outer)
      const fine = clampWingWalk(coarse.x, coarse.z, PLAYER_R)
      return { x: fine.x, z: fine.z }
    },
    [outer],
  )

  const camClamp = useMemo(
    () => ({
      minX: outer.minX + GROUNDED.camWallPad,
      maxX: outer.maxX - GROUNDED.camWallPad,
      minZ: outer.minZ + GROUNDED.camWallPad,
      maxZ: outer.maxZ - GROUNDED.camWallPad,
    }),
    [outer],
  )

  const respawn = (botId: string) => {
    const spawn = spawnBehindBot(botId)
    resetGroundedState(state.current, spawn.position[0], spawn.position[2], spawn.yaw, 0.08)
    camera.position.copy(state.current.camPos)
    lastRoom.current = spawn.room?.botId ?? null
  }

  useEffect(() => {
    if (!active) {
      locked.current = false
      dragging.current = false
      if (document.pointerLockElement) document.exitPointerLock()
      hintRef.current = ''
      onHintChange?.('')
      return
    }
    respawn(focusBotId)
    onHintChange?.(defaultWalkHint(false))
  }, [active, focusBotId]) // eslint-disable-line react-hooks/exhaustive-deps

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
      if (k === ' ' || k === 'spacebar') queueJump(state.current)
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
      applyLookDelta(state.current, e.movementX, e.movementY)
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
      if (document.pointerLockElement === el) document.exitPointerLock()
      keys.current = {}
    }
  }, [active, gl])

  useFrame((_, rawDt) => {
    if (!active) return
    const s = state.current
    const pose = stepGroundedWalk(s, {
      dt: rawDt,
      keys: keys.current,
      obstacles,
      clampXZ,
      camClamp,
      radius: PLAYER_R,
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

    const room = roomAtPosition(s.pos.x, s.pos.z)
    if (room && room.botId !== lastRoom.current) {
      lastRoom.current = room.botId
      onEnterRoom?.(room.botId)
    }

    const hint = defaultWalkHint(locked.current)
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  if (!active) return null

  return (
    <group ref={body}>
      <mesh position={[0, GROUNDED.bodyH * 0.42, 0]} castShadow={false}>
        <capsuleGeometry args={[GROUNDED.capsuleR * 0.75, GROUNDED.bodyH * 0.5, 5, 10]} />
        <meshStandardMaterial
          color="#5ad4e8"
          roughness={0.4}
          metalness={0.35}
          emissive="#1a8098"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[0, GROUNDED.bodyH * 0.92, 0]}>
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
