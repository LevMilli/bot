/**
 * Vault hall walk bounds + obstacle helpers for the grounded player.
 * Shared WalkBounds / resolveObstacles also power the trading-wing walker.
 */

export const BANK_AISLE_HALF = 3.35
export const BANK_LANE_HALF = 0.58
export const BANK_Z_BACK = -11.5
export const BANK_Z_FRONT = 7.5
export const BANK_HALL_HALF_W = 6.1

export type WalkBounds = {
  minX: number
  maxX: number
  minZ: number
  maxZ: number
}

/** Axis-aligned obstacle on the floor (desks, cabinets, door slabs). */
export type FloorObstacle = {
  minX: number
  maxX: number
  minZ: number
  maxZ: number
}

/** Clear aisle half-width (world X) — inside the rope mouths. */
export function aisleClearHalf(aisleHalf = BANK_AISLE_HALF, laneHalf = BANK_LANE_HALF): number {
  return Math.max(0.35, aisleHalf - laneHalf - 0.45)
}

/** Full floor rectangle inside the vault walls (player capsule radius inset). */
export function vaultFloorBounds(
  hallHalfW = BANK_HALL_HALF_W,
  zBack = BANK_Z_BACK,
  zFront = BANK_Z_FRONT,
  radius = 0.35,
): WalkBounds {
  return {
    minX: -hallHalfW + radius + 0.25,
    maxX: hallHalfW - radius - 0.25,
    minZ: zBack + 1.6 + radius,
    maxZ: zFront - 0.85 - radius,
  }
}

export function clampToBounds(x: number, z: number, b: WalkBounds): { x: number; z: number } {
  return {
    x: Math.min(b.maxX, Math.max(b.minX, x)),
    z: Math.min(b.maxZ, Math.max(b.minZ, z)),
  }
}

/** Push a point out of an AABB, preferring the shallowest axis. */
export function resolveObstacle(
  x: number,
  z: number,
  radius: number,
  ob: FloorObstacle,
): { x: number; z: number; hit: boolean } {
  const nearestX = Math.min(ob.maxX, Math.max(ob.minX, x))
  const nearestZ = Math.min(ob.maxZ, Math.max(ob.minZ, z))
  // If center is inside the box, push out on the shallowest face.
  if (x >= ob.minX && x <= ob.maxX && z >= ob.minZ && z <= ob.maxZ) {
    const left = x - ob.minX
    const right = ob.maxX - x
    const back = z - ob.minZ
    const front = ob.maxZ - z
    const m = Math.min(left, right, back, front)
    if (m === left) return { x: ob.minX - radius, z, hit: true }
    if (m === right) return { x: ob.maxX + radius, z, hit: true }
    if (m === back) return { x, z: ob.minZ - radius, hit: true }
    return { x, z: ob.maxZ + radius, hit: true }
  }
  const dx = x - nearestX
  const dz = z - nearestZ
  const d2 = dx * dx + dz * dz
  if (d2 >= radius * radius || d2 < 1e-8) return { x, z, hit: false }
  const d = Math.sqrt(d2)
  const push = (radius - d) / d
  return { x: x + dx * push, z: z + dz * push, hit: true }
}

export function resolveObstacles(
  x: number,
  z: number,
  radius: number,
  obstacles: FloorObstacle[],
): { x: number; z: number } {
  let nx = x
  let nz = z
  for (let pass = 0; pass < 2; pass++) {
    for (const ob of obstacles) {
      const r = resolveObstacle(nx, nz, radius, ob)
      nx = r.x
      nz = r.z
    }
  }
  return { x: nx, z: nz }
}

/** @deprecated Prefer vaultFloorBounds + clampToBounds for free player walk. */
export function clampBankWalk(
  x: number,
  z: number,
  opts?: { aisleHalf?: number; laneHalf?: number; zBack?: number; zFront?: number },
): { x: number; z: number } {
  const maxX = aisleClearHalf(opts?.aisleHalf, opts?.laneHalf)
  const zBack = opts?.zBack ?? BANK_Z_BACK
  const zFront = opts?.zFront ?? BANK_Z_FRONT
  return clampToBounds(x, z, {
    minX: -maxX,
    maxX,
    minZ: zBack + 1.35,
    maxZ: zFront - 0.9,
  })
}
