/**
 * Vault hall walk bounds — free movement on the floor, blocked by walls.
 * Designed so the same helper can later bound plaza / tower floors.
 */

export const BANK_AISLE_HALF = 3.25
export const BANK_LANE_HALF = 0.7
export const BANK_Z_BACK = -18
export const BANK_Z_FRONT = 14
export const BANK_HALL_HALF_W = 15.6

export type WalkBounds = {
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
    minX: -hallHalfW + radius + 0.35,
    maxX: hallHalfW - radius - 0.35,
    minZ: zBack + 1.5 + radius,
    maxZ: zFront - 1.1 - radius,
  }
}

export function clampToBounds(x: number, z: number, b: WalkBounds): { x: number; z: number } {
  return {
    x: Math.min(b.maxX, Math.max(b.minX, x)),
    z: Math.min(b.maxZ, Math.max(b.minZ, z)),
  }
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
