/** Shared plaza geometry — rail loop + back avenue (no front road). */

export const RAIL_R = 12.4
export const PLAZA_RAIL_R = RAIL_R
export const RAIL_Z_OFF = -1
export const RAIL_GAUGE = 0.85
/** Keep building footprints clear of ballast + rails. */
export const RAIL_CLEAR = 1.85

/** E–W avenue behind the plaza — crosses the rear of the rail loop. */
export const BACK_ROAD_Z = -11.15
export const BACK_ROAD_HALF_W = 1.35
export const BACK_ROAD_HALF_LEN = 22

export function distFromRailCenter(x: number, z: number) {
  return Math.hypot(x, z - RAIL_Z_OFF)
}

/** Signed gap from rail centerline (0 = on the rails). */
export function railGap(x: number, z: number) {
  return Math.abs(distFromRailCenter(x, z) - RAIL_R)
}

export function hitsRail(x: number, z: number, halfW: number) {
  return railGap(x, z) < RAIL_CLEAR + halfW
}

export function hitsBackRoad(x: number, z: number, halfW: number) {
  if (Math.abs(x) > BACK_ROAD_HALF_LEN + halfW) return false
  return Math.abs(z - BACK_ROAD_Z) < BACK_ROAD_HALF_W + halfW
}

/** Prefer the plaza interior — pull inward off the rail band. */
export function clearFromRail(x: number, z: number, halfW: number): [number, number] {
  const d = distFromRailCenter(x, z)
  const minInside = RAIL_R - RAIL_CLEAR - halfW
  const minOutside = RAIL_R + RAIL_CLEAR + halfW
  if (d < 1e-6) return [0, RAIL_Z_OFF + minInside]
  if (d >= minInside && d <= minOutside) {
    // Inside the band — pull into the plaza (never push onto the front arc).
    const s = minInside / d
    return [x * s, RAIL_Z_OFF + (z - RAIL_Z_OFF) * s]
  }
  return [x, z]
}

/** Nudge off the back avenue (toward plaza / +z). */
export function clearFromBackRoad(x: number, z: number, halfW: number): [number, number] {
  if (!hitsBackRoad(x, z, halfW)) return [x, z]
  const edge = BACK_ROAD_Z + BACK_ROAD_HALF_W + halfW + 0.2
  return [x, Math.max(z, edge)]
}
