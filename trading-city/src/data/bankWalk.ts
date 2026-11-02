/**
 * Bank hall walk bounds — keep the camera target in the clear aisle.
 * No clip through teller desks (side channels) or the vault door (−Z).
 */
export const BANK_AISLE_HALF = 3.25
export const BANK_LANE_HALF = 0.7
export const BANK_Z_BACK = -8.45
export const BANK_Z_FRONT = 5.75

/** Clear aisle half-width (world X) — inside the rope mouths. */
export function aisleClearHalf(aisleHalf = BANK_AISLE_HALF, laneHalf = BANK_LANE_HALF): number {
  return Math.max(0.35, aisleHalf - laneHalf - 0.45)
}

export function clampBankWalk(
  x: number,
  z: number,
  opts?: { aisleHalf?: number; laneHalf?: number; zBack?: number; zFront?: number },
): { x: number; z: number } {
  const maxX = aisleClearHalf(opts?.aisleHalf, opts?.laneHalf)
  const zBack = opts?.zBack ?? BANK_Z_BACK
  const zFront = opts?.zFront ?? BANK_Z_FRONT
  const minZ = zBack + 1.35 // clear of vault door slab
  const maxZ = zFront - 0.9
  return {
    x: Math.min(maxX, Math.max(-maxX, x)),
    z: Math.min(maxZ, Math.max(minZ, z)),
  }
}
