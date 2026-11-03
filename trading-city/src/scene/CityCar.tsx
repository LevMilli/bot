import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, MeshBasicMaterial } from 'three'
import type { BotPose } from '../data/botPose'
import { BotFigure } from './BotFigure'
import { BACK_ROAD_HALF_LEN, BACK_ROAD_Z } from './plazaLayout'

export type CarOccupancy = 'empty' | 'driver' | 'couple' | 'family'

type Props = {
  position: [number, number, number]
  /** Yaw in radians — forward is local −X. */
  rotation?: number
  color?: string
  accent?: string
  occupancy?: CarOccupancy
  /** Real pointLight wash — keep few for FPS. */
  castHeadlight?: boolean
  /** 0–1 fade for spawn/despawn */
  opacity?: number
  /** Spin wheels while moving */
  rolling?: boolean
}

const POSES: BotPose[] = ['waiting', 'researching', 'trading', 'winning']

/**
 * Sleek hover coupe. Forward = local −X.
 * Dark hull, purple light seam, and a thruster streak off the tail.
 */
export function CityCar({
  position,
  rotation = 0,
  color = '#0c0614',
  accent = '#c084fc',
  occupancy = 'driver',
  castHeadlight = false,
  opacity = 1,
  rolling = false,
}: Props) {
  const hover = useRef<Group>(null)
  const trail = useRef<MeshBasicMaterial>(null)
  const phase = useMemo(() => accent.charCodeAt(1) * 0.17, [accent])

  const passengers = useMemo(() => {
    if (occupancy === 'empty') return [] as { seat: [number, number, number]; pose: BotPose }[]
    if (occupancy === 'driver')
      return [{ seat: [0.02, 0.3, 0.08] as [number, number, number], pose: POSES[0] }]
    if (occupancy === 'couple')
      return [
        { seat: [0.02, 0.3, 0.08] as [number, number, number], pose: POSES[1] },
        { seat: [0.02, 0.3, -0.08] as [number, number, number], pose: POSES[2] },
      ]
    return [
      { seat: [0.06, 0.3, 0.08] as [number, number, number], pose: POSES[0] },
      { seat: [0.06, 0.3, -0.08] as [number, number, number], pose: POSES[3] },
      { seat: [-0.16, 0.28, 0] as [number, number, number], pose: POSES[1] },
    ]
  }, [occupancy])

  const bodyOpacity = Math.max(0, Math.min(1, opacity))
  const visible = bodyOpacity > 0.02

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (hover.current) {
      hover.current.position.y = rolling ? Math.sin(t * 1.6 + phase) * 0.055 : 0
    }
    if (trail.current) {
      const pulse = rolling ? 0.45 + Math.sin(t * 10 + phase) * 0.22 : 0.55
      trail.current.opacity = pulse * bodyOpacity
    }
  })

  return (
    <group position={position} rotation={[0, rotation, 0]} visible={visible}>
      <group ref={hover}>
        {/* Soft purple cushion — an oval, not a slab. */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0.05, 0.03, 0]} scale={[1.45, 0.62, 1]}>
          <circleGeometry args={[0.72, 24]} />
          <meshBasicMaterial color={accent} transparent opacity={0.4 * bodyOpacity} depthWrite={false} toneMapped={false} />
        </mesh>

        {/* Rounded hull. Cylinder axis is turned onto X; scale flattens it. Nose is −X. */}
        <mesh position={[0.08, 0.2, 0]} rotation={[0, 0, Math.PI / 2]} scale={[0.55, 1, 0.82]}>
          <cylinderGeometry args={[0.3, 0.3, 1.65, 22]} />
          <meshStandardMaterial
            color={color}
            metalness={0.62}
            roughness={0.26}
            emissive="#3b1468"
            emissiveIntensity={0.22}
            transparent
            opacity={bodyOpacity}
          />
        </mesh>
        <mesh position={[-1.02, 0.18, 0]} rotation={[0, 0, Math.PI / 2]} scale={[0.42, 1, 0.68]}>
          <coneGeometry args={[0.3, 0.95, 18]} />
          <meshStandardMaterial
            color={color}
            metalness={0.58}
            roughness={0.28}
            emissive="#1a0830"
            emissiveIntensity={0.24}
            transparent
            opacity={bodyOpacity}
          />
        </mesh>
        <mesh position={[0.95, 0.19, 0]} scale={[0.42, 0.26, 0.36]}>
          <sphereGeometry args={[0.42, 16, 12]} />
          <meshStandardMaterial
            color={color}
            metalness={0.6}
            roughness={0.26}
            emissive="#3b1468"
            emissiveIntensity={0.18}
            transparent
            opacity={bodyOpacity}
          />
        </mesh>

        {([-1, 1] as const).map((side) => (
          <mesh key={`seam-${side}`} position={[0.02, 0.16, side * 0.22]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.012, 0.012, 1.7, 8]} />
            <meshBasicMaterial color={accent} transparent opacity={bodyOpacity} toneMapped={false} />
          </mesh>
        ))}

        <mesh position={[-0.12, 0.34, 0]} scale={[0.72, 0.32, 0.46]}>
          <sphereGeometry args={[0.42, 18, 14]} />
          <meshStandardMaterial
            color="#14081f"
            metalness={0.78}
            roughness={0.1}
            emissive={accent}
            emissiveIntensity={0.32}
            transparent
            opacity={bodyOpacity}
          />
        </mesh>
        <mesh position={[-0.42, 0.32, 0]} rotation={[0, 0, Math.PI / 2]} scale={[0.28, 1, 0.4]}>
          <sphereGeometry args={[0.22, 14, 10]} />
          <meshStandardMaterial
            color="#0c0614"
            metalness={0.84}
            roughness={0.08}
            emissive={accent}
            emissiveIntensity={0.45}
            transparent
            opacity={bodyOpacity}
          />
        </mesh>

        {([-1, 1] as const).map((side) => (
          <mesh key={`lamp-${side}`} position={[-1.42, 0.17, side * 0.1]}>
            <sphereGeometry args={[0.035, 10, 8]} />
            <meshBasicMaterial color="#f3e8ff" transparent opacity={bodyOpacity} toneMapped={false} />
          </mesh>
        ))}
        {castHeadlight && bodyOpacity > 0.4 && (
          <pointLight position={[-1.5, 0.18, 0]} intensity={0.8 * bodyOpacity} distance={4.5} color={accent} decay={2} />
        )}

        {([-1, 1] as const).map((side) => (
          <mesh key={`port-${side}`} position={[1.12, 0.17, side * 0.12]}>
            <sphereGeometry args={[0.05, 10, 8]} />
            <meshStandardMaterial color="#12081c" emissive={accent} emissiveIntensity={0.85} transparent opacity={bodyOpacity} />
          </mesh>
        ))}
        {/* Thruster streak — a tapering cone, not a box. */}
        <mesh position={[1.85, 0.16, 0]} rotation={[0, 0, -Math.PI / 2]} scale={[0.28, 1, 0.16]}>
          <coneGeometry args={[0.32, 1.7, 14]} />
          <meshBasicMaterial
            ref={trail}
            color={accent}
            transparent
            opacity={0.55 * bodyOpacity}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
        <mesh position={[1.55, 0.16, 0]} rotation={[0, 0, -Math.PI / 2]} scale={[0.1, 1, 0.06]}>
          <coneGeometry args={[0.2, 1.15, 10]} />
          <meshBasicMaterial color="#f3e8ff" transparent opacity={0.8 * bodyOpacity} depthWrite={false} toneMapped={false} />
        </mesh>

        {passengers.map((p, i) => (
          <group key={i} position={[p.seat[0] - 0.02, 0.24, p.seat[2]]} scale={0.15} rotation={[0, -Math.PI / 2, 0]}>
            <BotFigure pose={p.pose} seated />
          </group>
        ))}
      </group>
    </group>
  )
}

type TrafficCar = {
  slot: number
  dir: -1 | 1
  x: number
  speed: number
  color: string
  accent: string
  occupancy: CarOccupancy
  opacity: number
  phase: 'cruise' | 'fadeOut' | 'fadeIn'
  gen: number
}

const PALETTE = [
  { color: '#0c0614', accent: '#c084fc', occupancy: 'family' as const },
  { color: '#100818', accent: '#d4a0ff', occupancy: 'couple' as const },
  { color: '#14081c', accent: '#b967ff', occupancy: 'driver' as const },
  { color: '#0a0412', accent: '#e9d5ff', occupancy: 'couple' as const },
]

const LANE = 0.72
/** Nose-to-tail gap along the avenue (hull plus the thruster streak). */
const MIN_GAP = 4.2
const ROAD_END = BACK_ROAD_HALF_LEN - 1.2
const FADE_DIST = 2.8

function makeCar(slot: number, dir: -1 | 1, x: number, gen: number): TrafficCar {
  const pal = PALETTE[(slot + gen) % PALETTE.length]
  return {
    slot,
    dir,
    x,
    speed: 3.4 + (slot % 2) * 0.35,
    color: pal.color,
    accent: pal.accent,
    occupancy: pal.occupancy,
    opacity: 1,
    phase: 'cruise',
    gen,
  }
}

/** True if `x` is clear of every same-direction car (except optional skip slot). */
function spawnClear(cars: TrafficCar[], dir: -1 | 1, x: number, skipSlot: number) {
  for (const o of cars) {
    if (o.slot === skipSlot || o.dir !== dir) continue
    if (Math.abs(o.x - x) < MIN_GAP) return false
  }
  return true
}

/** Find a spawn X at the lane entrance that does not stack on another car. */
function clearSpawnX(cars: TrafficCar[], dir: -1 | 1, skipSlot: number) {
  const start = dir < 0 ? ROAD_END : -ROAD_END
  // Walk inward from the entrance until we clear everyone ahead in this lane.
  for (let step = 0; step < 12; step++) {
    const x = start - dir * step * (MIN_GAP * 0.55)
    if (Math.abs(x) > ROAD_END + 0.5) continue
    if (spawnClear(cars, dir, x, skipSlot)) return x
  }
  // Last resort: park just inside the fade zone, still spaced from peers.
  return start - dir * MIN_GAP
}

/**
 * Four hover cars on the back avenue, lifted into two air lanes, looping with fade.
 * Same-lane cars keep a hard MIN_GAP so they never intersect.
 */
export function AvenueTraffic({ deckY = 1.35 }: { deckY?: number }) {
  // Two per lane, seeded far apart.
  const sim = useRef<TrafficCar[]>([
    makeCar(0, -1, 16, 0),
    makeCar(1, -1, 6, 0),
    makeCar(2, 1, 2, 0),
    makeCar(3, 1, 12, 0),
  ])
  const [snap, setSnap] = useState(() => sim.current.map((c) => ({ ...c })))
  const acc = useRef(0)

  useFrame((_, dt) => {
    const cars = sim.current

    // 1) Integrate motion
    for (const c of cars) {
      c.x += c.dir * c.speed * dt
    }

    // 2) Same-lane separation — never let a follower overlap / pass the leader.
    for (const dir of [-1, 1] as const) {
      const lane = cars.filter((c) => c.dir === dir).sort((a, b) => (dir < 0 ? a.x - b.x : b.x - a.x))
      // Sorted so index 0 is the lead car (furthest along travel direction).
      for (let i = 1; i < lane.length; i++) {
        const lead = lane[i - 1]
        const follow = lane[i]
        // Lead is ahead: for dir=-1 ahead means smaller x; for dir=+1 ahead means larger x.
        const aheadX = lead.x
        const minFollowX = dir < 0 ? aheadX + MIN_GAP : aheadX - MIN_GAP
        if (dir < 0 && follow.x < minFollowX) {
          follow.x = minFollowX
          follow.speed = Math.min(follow.speed, lead.speed * 0.92)
        } else if (dir > 0 && follow.x > minFollowX) {
          follow.x = minFollowX
          follow.speed = Math.min(follow.speed, lead.speed * 0.92)
        }
      }
    }

    // 3) End fade / respawn with clearance check
    for (const c of cars) {
      const end = c.dir < 0 ? -ROAD_END : ROAD_END
      const start = c.dir < 0 ? ROAD_END : -ROAD_END
      const distToEnd = c.dir < 0 ? c.x - end : end - c.x

      if (c.phase === 'cruise' && distToEnd < FADE_DIST) c.phase = 'fadeOut'

      if (c.phase === 'fadeOut') {
        c.opacity = Math.max(0, distToEnd / FADE_DIST)
        if (c.opacity <= 0.02 || distToEnd < 0) {
          // Hold invisible until the entrance is clear, then fade in.
          const x = clearSpawnX(cars, c.dir, c.slot)
          if (!spawnClear(cars, c.dir, x, c.slot)) {
            c.opacity = 0
            c.x = x
            continue
          }
          c.gen += 1
          const pal = PALETTE[(c.slot + c.gen) % PALETTE.length]
          c.x = x
          c.speed = 3.1 + Math.random() * 0.7
          c.color = pal.color
          c.accent = pal.accent
          c.occupancy = pal.occupancy
          c.opacity = 0
          c.phase = 'fadeIn'
        }
      } else if (c.phase === 'fadeIn') {
        const distFromStart = Math.abs(c.x - start)
        c.opacity = Math.min(1, Math.max(0.05, distFromStart / FADE_DIST))
        if (c.opacity >= 0.98) {
          c.opacity = 1
          c.phase = 'cruise'
        }
      } else {
        c.opacity = 1
      }
    }

    acc.current += dt
    if (acc.current >= 0.05) {
      acc.current = 0
      setSnap(cars.map((c) => ({ ...c })))
    }
  })

  return (
    <group>
      {snap.map((c) => {
        const yaw = c.dir < 0 ? 0 : Math.PI
        const z = c.dir < 0 ? BACK_ROAD_Z - LANE : BACK_ROAD_Z + LANE
        const fly = c.dir < 0 ? 1.35 : 1.85
        return (
          <CityCar
            key={c.slot}
            position={[c.x, deckY + fly, z]}
            rotation={yaw}
            color={c.color}
            accent={c.accent}
            occupancy={c.occupancy}
            castHeadlight={c.slot < 2}
            opacity={c.opacity}
            rolling
          />
        )
      })}
    </group>
  )
}
