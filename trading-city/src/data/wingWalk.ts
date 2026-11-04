/**
 * Trading-wing walk geometry for Plan A (linear spine).
 * Continuous floor: hallway + open doorways into five worker suites + boss.
 * Locomotion is shared vault UX via groundedWalk (W/S · A/D turn · jump);
 * this module owns bounds / obstacles / spawn / room detection only.
 */

import type { FloorObstacle, WalkBounds } from './bankWalk'
import { activeWingRooms, type WingRoom } from './officeWingLayout'

export const WING_HALL = {
  xMin: -1.2,
  /** Extends to the boss doorway (boss center 35.2 − room depth 4). */
  xMax: 31.4,
  zMin: -1.55,
  zMax: 1.55,
  wallH: 3.35,
}

export const ROOM_HALF_W = 5.1
export const ROOM_HALF_D = 4.0
/** Open doorway half-width from room into hall. */
export const DOOR_HALF = 1.05
export const PLAYER_R = 0.32

/** Local-space spawn: stand behind the seated bot, looking at their back / screens. */
export const SPAWN_BEHIND_LOCAL: [number, number, number] = [0.05, 0, 1.85]
export const SPAWN_LOOK_LOCAL: [number, number, number] = [0, 1.35, -0.4]

export function suiteWorld(
  room: WingRoom,
  local: [number, number, number],
  scale = 0.62,
): [number, number, number] {
  const [lx, ly, lz] = local
  const c = Math.cos(room.yaw)
  const sn = Math.sin(room.yaw)
  return [
    room.position[0] + c * lx * scale + sn * lz * scale,
    room.position[1] + ly * scale,
    room.position[2] - sn * lx * scale + c * lz * scale,
  ]
}

export function spawnBehindBot(botId: string): {
  position: [number, number, number]
  yaw: number
  room: WingRoom | null
} {
  const room = activeWingRooms().find((r) => r.botId === botId) || activeWingRooms()[0] || null
  if (!room) return { position: [2, 0, 0], yaw: Math.PI / 2, room: null }
  const position = suiteWorld(room, SPAWN_BEHIND_LOCAL)
  // Face the desk / bot (toward local −Z after room yaw).
  const yaw = room.yaw + Math.PI
  return { position, yaw, room }
}

/** Loose AABB covering hall + all suites (coarse clamp before corridor filter). */
export function wingOuterBounds(radius = PLAYER_R): WalkBounds {
  return {
    minX: WING_HALL.xMin - ROOM_HALF_D + radius,
    maxX: WING_HALL.xMax + ROOM_HALF_W,
    minZ: -ROOM_HALF_D - ROOM_HALF_W,
    maxZ: ROOM_HALF_D + ROOM_HALF_W,
  }
}

function roomFootprint(room: WingRoom): WalkBounds {
  // Rooms extend mostly along local ±X (width) and toward −Z (window) / +Z (door→hall).
  const hw = ROOM_HALF_W
  const hd = ROOM_HALF_D
  const corners: [number, number][] = [
    [-hw, -hd],
    [hw, -hd],
    [-hw, hd],
    [hw, hd],
  ]
  const c = Math.cos(room.yaw)
  const sn = Math.sin(room.yaw)
  let minX = Infinity
  let maxX = -Infinity
  let minZ = Infinity
  let maxZ = -Infinity
  for (const [lx, lz] of corners) {
    const x = room.position[0] + c * lx + sn * lz
    const z = room.position[2] - sn * lx + c * lz
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minZ = Math.min(minZ, z)
    maxZ = Math.max(maxZ, z)
  }
  return { minX, maxX, minZ, maxZ }
}

function inBounds(x: number, z: number, b: WalkBounds, pad = 0): boolean {
  return x >= b.minX - pad && x <= b.maxX + pad && z >= b.minZ - pad && z <= b.maxZ + pad
}

function inHall(x: number, z: number, radius: number): boolean {
  return (
    x >= WING_HALL.xMin + radius &&
    x <= WING_HALL.xMax - radius &&
    z >= WING_HALL.zMin + radius &&
    z <= WING_HALL.zMax - radius
  )
}

/** Door corridor: room → hall open gap, in world space along the hallway face. */
function inDoorLane(room: WingRoom, x: number, z: number, radius: number): boolean {
  const doorLocal: [number, number, number] = [0, 0, ROOM_HALF_D - 0.15]
  const [dx, , dz] = suiteWorld(room, doorLocal, 1)
  // Lane aligned with hallway (±X for side rooms, ±Z for boss end).
  if (room.side === 'end') {
    return Math.abs(z - dz) <= DOOR_HALF + radius && Math.abs(x - dx) <= 1.4 + radius
  }
  return Math.abs(x - dx) <= DOOR_HALF + 0.35 + radius && Math.abs(z - dz) <= 1.35 + radius
}

/**
 * Soft walkable test: hall OR any suite footprint OR door blend.
 * Used after physics step to pull the player back if they leave the mesh.
 */
export function clampWingWalk(
  x: number,
  z: number,
  radius = PLAYER_R,
): { x: number; z: number; zone: 'hall' | 'suite' | 'door' | 'void' } {
  if (inHall(x, z, radius)) return { x, z, zone: 'hall' }
  const rooms = activeWingRooms()
  for (const room of rooms) {
    if (inDoorLane(room, x, z, radius)) return { x, z, zone: 'door' }
    const fp = roomFootprint(room)
    if (inBounds(x, z, fp, -radius * 0.5)) return { x, z, zone: 'suite' }
  }
  // Pull toward nearest hall centerline.
  const cx = Math.min(WING_HALL.xMax - radius, Math.max(WING_HALL.xMin + radius, x))
  const cz = Math.min(WING_HALL.zMax - radius, Math.max(WING_HALL.zMin + radius, z))
  return { x: cx, z: cz, zone: 'void' }
}

/** Desk / furniture blockers so the walker can't clip the main station. */
export function wingDeskObstacles(): FloorObstacle[] {
  const out: FloorObstacle[] = []
  for (const room of activeWingRooms()) {
    // Desk block in front of the bot (local origin area).
    const a = suiteWorld(room, [-1.6, 0, -0.9], 0.62)
    const b = suiteWorld(room, [1.6, 0, 0.55], 0.62)
    out.push({
      minX: Math.min(a[0], b[0]) - 0.15,
      maxX: Math.max(a[0], b[0]) + 0.15,
      minZ: Math.min(a[2], b[2]) - 0.15,
      maxZ: Math.max(a[2], b[2]) + 0.15,
    })
  }
  return out
}

/** Which suite the player is standing in (for live desk LOD / selected bot). */
export function roomAtPosition(x: number, z: number): WingRoom | null {
  for (const room of activeWingRooms()) {
    if (inDoorLane(room, x, z, PLAYER_R)) continue
    if (inBounds(x, z, roomFootprint(room), -0.2)) return room
  }
  return null
}
