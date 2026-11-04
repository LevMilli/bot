import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
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
  DESK_INTERACT_R,
  PLAYER_R,
  clampWingWalk,
  deskInteractPoint,
  roomAtPosition,
  spawnForMode,
  wingDeskObstacles,
  wingOuterBounds,
  type WingSpawnMode,
} from '../data/wingWalk'

type Props = {
  active: boolean
  /** Tower / teller bot we entered from — spawn behind this desk bot (once per entry). */
  focusBotId: string
  /** FloorNavMenu zone — hall/boss teleport without leaving the wing. */
  spawnMode?: WingSpawnMode
  onEnterRoom?: (botId: string) => void
  /** E near the live desk opens monitor lightbox (vault-style interact). */
  onOpenScreens?: () => void
  onHintChange?: (hint: string) => void
}

/** Suite/boss: slight down-pitch so monitors fill the frame, not the city window. */
function spawnPitchFor(mode: WingSpawnMode) {
  return mode === 'hall' ? 0.02 : -0.18
}

/**
 * Trading-wing free walk using the same vault teller grounded physics
 * (W/S walk · A/D turn · Space jump · mouse look · Shift sprint).
 * Camera is first-person (no body mesh) so the suite desk reads as the hero —
 * vault PlayerBot stays over-shoulder; locomotion still comes only from groundedWalk.
 */
export function WingWalker({
  active,
  focusBotId,
  spawnMode = 'suite',
  onEnterRoom,
  onOpenScreens,
  onHintChange,
}: Props) {
  const { camera, gl } = useThree()
  const state = useRef<GroundedState>(createGroundedState())
  const keys = useRef<Record<string, boolean>>({})
  const dragging = useRef(false)
  const locked = useRef(false)
  const lastRoom = useRef<string | null>(null)
  const nearDesk = useRef(false)
  const hintRef = useRef('')
  const bobY = useRef(0)

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

  const snapEyeCam = (mode: WingSpawnMode) => {
    const s = state.current
    const look = mode === 'hall' ? 5.5 : 2.35
    camera.position.set(s.pos.x, s.pos.y + GROUNDED.eyeH, s.pos.z)
    camera.lookAt(
      s.pos.x + Math.sin(s.yaw) * look,
      s.pos.y + GROUNDED.eyeH + s.pitch * 2.2,
      s.pos.z + Math.cos(s.yaw) * look,
    )
  }

  const respawn = (botId: string, mode: WingSpawnMode) => {
    const spawn = spawnForMode(mode, botId)
    resetGroundedState(
      state.current,
      spawn.position[0],
      spawn.position[2],
      spawn.yaw,
      spawnPitchFor(mode),
    )
    // Snap eye cam immediately so Hallway/Boss never flash a black void.
    snapEyeCam(mode)
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
    respawn(focusBotId, spawnMode)
    onHintChange?.(defaultWalkHint(false))
  }, [active, focusBotId, spawnMode]) // eslint-disable-line react-hooks/exhaustive-deps

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
        if (nearDesk.current) onOpenScreens?.()
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
  }, [active, gl, onOpenScreens])

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

    bobY.current = Math.abs(pose.bob) * 0.12
    // First-person eye cam — ignore over-shoulder camPos from groundedWalk.
    const lookDist = 2.6
    camera.position.set(s.pos.x, s.pos.y + GROUNDED.eyeH + bobY.current, s.pos.z)
    camera.lookAt(
      s.pos.x + Math.sin(s.yaw) * lookDist,
      s.pos.y + GROUNDED.eyeH + s.pitch * 2.4,
      s.pos.z + Math.cos(s.yaw) * lookDist,
    )

    const room = roomAtPosition(s.pos.x, s.pos.z)
    if (room && room.botId !== lastRoom.current) {
      lastRoom.current = room.botId
      onEnterRoom?.(room.botId)
    }

    // E · open screens when standing at the live suite desk (vault-style nearest interact).
    const liveId = room?.botId ?? lastRoom.current
    const desk = liveId ? deskInteractPoint(liveId) : null
    const atDesk = Boolean(
      desk && Math.hypot(desk.x - s.pos.x, desk.z - s.pos.z) <= DESK_INTERACT_R,
    )
    nearDesk.current = atDesk

    const hint = defaultWalkHint(locked.current, atDesk ? 'E · open desk screens' : null)
    if (hint !== hintRef.current) {
      hintRef.current = hint
      onHintChange?.(hint)
    }
  })

  // No body mesh — FPV keeps the suite desk / hall as the visual hero.
  return null
}
