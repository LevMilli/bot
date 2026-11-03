/**
 * Office-floor walk bounds — suite, hallway, and boss chamber.
 * Same motion model as bankWalk: clamp the orbit target, then drag the camera with it.
 */

export const OFFICE_SUITE = {
  xMin: -6.8,
  xMax: 6.8,
  zMin: -2.6,
  zMax: 4.2,
}

export const OFFICE_HALL = {
  xMin: -1.55,
  xMax: 1.55,
  zMin: 4.6,
  zMax: 22.4,
}

export const OFFICE_BOSS = {
  xMin: -3.6,
  xMax: 3.6,
  zMin: 22.2,
  zMax: 29.2,
}

export type OfficeWalkZone = 'suite' | 'hall' | 'boss'

export function clampOfficeWalk(
  x: number,
  z: number,
  zone: OfficeWalkZone = 'hall',
): { x: number; z: number } {
  const b =
    zone === 'suite' ? OFFICE_SUITE : zone === 'boss' ? OFFICE_BOSS : OFFICE_HALL
  // Allow a soft corridor blend when walking suite ↔ hall through the glass door.
  if (zone === 'hall' || zone === 'suite') {
    const doorX = 1.1
    const inDoorLane = Math.abs(x) <= doorX
    if (inDoorLane && z > OFFICE_SUITE.zMax - 0.4 && z < OFFICE_HALL.zMin + 0.6) {
      return {
        x: Math.min(doorX, Math.max(-doorX, x)),
        z: Math.min(OFFICE_HALL.zMax, Math.max(OFFICE_SUITE.zMin, z)),
      }
    }
  }
  if (zone === 'hall' || zone === 'boss') {
    const doorX = 1.2
    if (Math.abs(x) <= doorX && z > OFFICE_HALL.zMax - 0.5 && z < OFFICE_BOSS.zMin + 0.5) {
      return {
        x: Math.min(doorX, Math.max(-doorX, x)),
        z: Math.min(OFFICE_BOSS.zMax, Math.max(OFFICE_HALL.zMin, z)),
      }
    }
  }
  return {
    x: Math.min(b.xMax, Math.max(b.xMin, x)),
    z: Math.min(b.zMax, Math.max(b.zMin, z)),
  }
}

export function officeZoneForZ(z: number): OfficeWalkZone {
  if (z >= 22.5) return 'boss'
  if (z >= 4.8) return 'hall'
  return 'suite'
}
