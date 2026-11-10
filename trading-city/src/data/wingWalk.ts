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
  /** Extends to the boss doorway (boss center 43.2 − room depth 4). */
  xMax: 39.2,
  zMin: -1.55,
  zMax: 1.55,
  wallH: 3.35,
}

export const ROOM_HALF_W = 5.1
export const ROOM_HALF_D = 4.0
/** Open doorway half-width from room into hall. */
export const DOOR_HALF = 1.05
export const PLAYER_R = 0.32
/** Desk props scale inside SuiteShell (shell itself stays unscaled). */
export const SUITE_CONTENT_SCALE = 0.62

/** Local-space spawn: stand behind the seated bot, looking at their back / screens.
 * Slightly closer than hall door so FPV fills with monitors, not the city glass. */
export const SPAWN_BEHIND_LOCAL: [number, number, number] = [0.05, 0, 1.15]
export const SPAWN_LOOK_LOCAL: [number, number, number] = [0, 1.15, -0.55]
/** Desk / monitor interact point (suite local, before SUITE_CONTENT_SCALE). */
export const DESK_INTERACT_LOCAL: [number, number, number] = [0.05, 0, 0.35]
/** Reach for E · open desk screens. */
export const DESK_INTERACT_R = 2.6

/** World XZ of the desk interact point for a tower bot's suite. */
export function deskInteractPoint(botId: string): { x: number; z: number } | null {
  const room = activeWingRooms().find((r) => r.botId === botId) || null
  if (!room) return null
  const [x, , z] = suiteWorld(room, DESK_INTERACT_LOCAL)
  return { x, z }
}

export function suiteWorld(
  room: WingRoom,
  local: [number, number, number],
  scale = SUITE_CONTENT_SCALE,
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

export type WingSpawnMode = 'suite' | 'hall' | 'boss'

/** Mid-hall spawn looking toward the boss end (+X) so the corridor reads immediately. */
export function spawnInHall(): {
  position: [number, number, number]
  yaw: number
  room: WingRoom | null
} {
  const x = Math.min(WING_HALL.xMax - 4, Math.max(WING_HALL.xMin + 3.5, 10))
  return { position: [x, 0, 0], yaw: Math.PI / 2, room: null }
}

/** Resolve suite / hall / boss spawn for FloorNavMenu teleports. */
export function spawnForMode(
  mode: WingSpawnMode,
  focusBotId: string,
): {
  position: [number, number, number]
  yaw: number
  room: WingRoom | null
} {
  if (mode === 'hall') return spawnInHall()
  if (mode === 'boss') return spawnBehindBot('kalshi-sized')
  return spawnBehindBot(focusBotId)
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

function dist2(ax: number, az: number, bx: number, bz: number) {
  const dx = ax - bx
  const dz = az - bz
  return dx * dx + dz * dz
}

/** Project (x,z) onto an AABB (inset by radius). */
function projectBounds(x: number, z: number, b: WalkBounds, radius: number) {
  return {
    x: Math.min(b.maxX - radius, Math.max(b.minX + radius, x)),
    z: Math.min(b.maxZ - radius, Math.max(b.minZ + radius, z)),
  }
}

/**
 * Soft walkable test: hall OR any suite footprint OR door blend.
 * Used after physics step to pull the player back if they leave the mesh.
 * Void recovery snaps to the nearest walkable point (suite/door/hall) — never
 * teleports a desk walker into the hall centerline.
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

  // Nearest walkable recovery — keep the camera inside the enclosed floor plan.
  let best = {
    x: Math.min(WING_HALL.xMax - radius, Math.max(WING_HALL.xMin + radius, x)),
    z: Math.min(WING_HALL.zMax - radius, Math.max(WING_HALL.zMin + radius, z)),
    d: Infinity as number,
  }
  const hallHit = projectBounds(
    x,
    z,
    {
      minX: WING_HALL.xMin,
      maxX: WING_HALL.xMax,
      minZ: WING_HALL.zMin,
      maxZ: WING_HALL.zMax,
    },
    radius,
  )
  best = { ...hallHit, d: dist2(x, z, hallHit.x, hallHit.z) }

  for (const room of rooms) {
    const fp = roomFootprint(room)
    const hit = projectBounds(x, z, fp, radius * 0.5)
    const d = dist2(x, z, hit.x, hit.z)
    if (d < best.d) best = { x: hit.x, z: hit.z, d }

    const doorLocal: [number, number, number] = [0, 0, ROOM_HALF_D - 0.15]
    const [dx, , dz] = suiteWorld(room, doorLocal, 1)
    const dd = dist2(x, z, dx, dz)
    if (dd < best.d) best = { x: dx, z: dz, d: dd }
  }

  // Guarantee the recovery point itself is walkable (never leave the model).
  if (inHall(best.x, best.z, radius)) return { x: best.x, z: best.z, zone: 'hall' }
  for (const room of rooms) {
    if (inDoorLane(room, best.x, best.z, radius)) return { x: best.x, z: best.z, zone: 'door' }
    if (inBounds(best.x, best.z, roomFootprint(room), -radius * 0.5)) {
      return { x: best.x, z: best.z, zone: 'suite' }
    }
  }
  return {
    x: Math.min(WING_HALL.xMax - radius, Math.max(WING_HALL.xMin + radius, x)),
    z: 0,
    zone: 'hall',
  }
}

/** Desk / furniture blockers so the walker can't clip the main station. */
export function wingDeskObstacles(): FloorObstacle[] {
  const out: FloorObstacle[] = []
  for (const room of activeWingRooms()) {
    // Desk block in front of the bot (local origin area).
    const a = suiteWorld(room, [-1.6, 0, -0.9])
    const b = suiteWorld(room, [1.6, 0, 0.55])
    out.push({
      minX: Math.min(a[0], b[0]) - 0.15,
      maxX: Math.max(a[0], b[0]) + 0.15,
      minZ: Math.min(a[2], b[2]) - 0.15,
      maxZ: Math.max(a[2], b[2]) + 0.15,
    })
  }
  return out
}

/**
 * Solid hall / suite shell slabs as obstacles — keeps the capsule inside the
 * enclosed floor plan even if clamp soft-edges are generous.
 */
export function wingEnclosureObstacles(): FloorObstacle[] {
  const out: FloorObstacle[] = []
  const t = 0.16
  const gap = DOOR_HALF + 0.2

  // Hall side walls with door gaps (same segmentation as HallCosmetics).
  for (const side of [-1, 1] as const) {
    const zWall = side < 0 ? WING_HALL.zMin : WING_HALL.zMax
    const doors = activeWingRooms()
      .filter((r) => r.side !== 'end')
      .filter((r) => {
        const doorZ = r.position[2] + Math.cos(r.yaw) * ROOM_HALF_D
        return Math.abs(doorZ - zWall) < 0.35
      })
      .map((r) => r.position[0])
      .sort((a, b) => a - b)
    let cursor = WING_HALL.xMin
    const pushSeg = (lo: number, hi: number) => {
      if (hi - lo < 0.1) return
      out.push({
        minX: lo,
        maxX: hi,
        minZ: zWall - t / 2,
        maxZ: zWall + t / 2,
      })
    }
    for (const dx of doors) {
      pushSeg(cursor, dx - gap)
      cursor = dx + gap
    }
    pushSeg(cursor, WING_HALL.xMax)
  }

  // Entry end wall.
  out.push({
    minX: WING_HALL.xMin - t,
    maxX: WING_HALL.xMin + t * 0.5,
    minZ: WING_HALL.zMin - 0.1,
    maxZ: WING_HALL.zMax + 0.1,
  })

  // Suite outer shells (window + sides) — door face left open.
  for (const room of activeWingRooms()) {
    const c = Math.cos(room.yaw)
    const sn = Math.sin(room.yaw)
    const corners = (lx: number, lz: number) => ({
      x: room.position[0] + c * lx + sn * lz,
      z: room.position[2] - sn * lx + c * lz,
    })
    // Window wall at local −D
    {
      const a = corners(-ROOM_HALF_W, -ROOM_HALF_D)
      const b = corners(ROOM_HALF_W, -ROOM_HALF_D)
      out.push({
        minX: Math.min(a.x, b.x) - t / 2,
        maxX: Math.max(a.x, b.x) + t / 2,
        minZ: Math.min(a.z, b.z) - t / 2,
        maxZ: Math.max(a.z, b.z) + t / 2,
      })
    }
    // Side walls at local ±W
    for (const sx of [-ROOM_HALF_W, ROOM_HALF_W] as const) {
      const a = corners(sx, -ROOM_HALF_D)
      const b = corners(sx, ROOM_HALF_D)
      out.push({
        minX: Math.min(a.x, b.x) - t / 2,
        maxX: Math.max(a.x, b.x) + t / 2,
        minZ: Math.min(a.z, b.z) - t / 2,
        maxZ: Math.max(a.z, b.z) + t / 2,
      })
    }
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
