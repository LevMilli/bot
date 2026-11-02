import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Group } from 'three'
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
 * Reusable SIGNAL-CITY street car (procedural R3F model).
 * Forward = local −X. Headlights / cones aim that way.
 */
export function CityCar({
  position,
  rotation = 0,
  color = '#2de2e6',
  accent = '#7ef9ff',
  occupancy = 'driver',
  castHeadlight = false,
  opacity = 1,
  rolling = false,
}: Props) {
  const wheelSpin = useRef(0)
  const wheelRefs = useRef<(Group | null)[]>([])

  const passengers = useMemo(() => {
    if (occupancy === 'empty') return [] as { seat: [number, number, number]; pose: BotPose }[]
    if (occupancy === 'driver')
      return [{ seat: [0.06, 0.22, 0.1] as [number, number, number], pose: POSES[0] }]
    if (occupancy === 'couple')
      return [
        { seat: [0.06, 0.22, 0.1] as [number, number, number], pose: POSES[1] },
        { seat: [0.06, 0.22, -0.1] as [number, number, number], pose: POSES[2] },
      ]
    return [
      { seat: [0.08, 0.22, 0.1] as [number, number, number], pose: POSES[0] },
      { seat: [0.08, 0.22, -0.1] as [number, number, number], pose: POSES[3] },
      { seat: [-0.22, 0.2, 0] as [number, number, number], pose: POSES[1] },
    ]
  }, [occupancy])

  useFrame((_, dt) => {
    if (!rolling) return
    wheelSpin.current += dt * 9
    for (const w of wheelRefs.current) {
      if (w) w.rotation.x = wheelSpin.current
    }
  })

  const bodyOpacity = Math.max(0, Math.min(1, opacity))
  const visible = bodyOpacity > 0.02

  return (
    <group position={position} rotation={[0, rotation, 0]} visible={visible}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <planeGeometry args={[1.35, 0.7]} />
        <meshBasicMaterial color={accent} transparent opacity={0.14 * bodyOpacity} depthWrite={false} />
      </mesh>

      <mesh position={[0, 0.2, 0]}>
        <boxGeometry args={[1.35, 0.22, 0.62]} />
        <meshStandardMaterial
          color={color}
          metalness={0.55}
          roughness={0.32}
          emissive={color}
          emissiveIntensity={0.12}
          transparent
          opacity={bodyOpacity}
        />
      </mesh>
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[1.38, 0.08, 0.64]} />
        <meshBasicMaterial color="#0a0e16" transparent opacity={bodyOpacity} />
      </mesh>
      <mesh position={[-0.42, 0.28, 0]}>
        <boxGeometry args={[0.42, 0.1, 0.58]} />
        <meshStandardMaterial color={color} metalness={0.5} roughness={0.35} transparent opacity={bodyOpacity} />
      </mesh>
      <mesh position={[0.08, 0.42, 0]}>
        <boxGeometry args={[0.62, 0.28, 0.56]} />
        <meshBasicMaterial color="#0c1018" transparent opacity={bodyOpacity} />
      </mesh>
      <mesh position={[-0.22, 0.42, 0]} rotation={[0, 0, -0.35]}>
        <boxGeometry args={[0.28, 0.22, 0.54]} />
        <meshBasicMaterial color="#9ee9ff" transparent opacity={0.35 * bodyOpacity} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0.38, 0.42, 0]} rotation={[0, 0, 0.28]}>
        <boxGeometry args={[0.22, 0.2, 0.54]} />
        <meshBasicMaterial color="#7ec8e0" transparent opacity={0.28 * bodyOpacity} depthWrite={false} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[0.06, 0.44, side * 0.29]}>
          <boxGeometry args={[0.48, 0.16, 0.03]} />
          <meshBasicMaterial color="#b8f0ff" transparent opacity={0.4 * bodyOpacity} depthWrite={false} toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[-0.7, 0.16, 0]}>
        <boxGeometry args={[0.08, 0.12, 0.66]} />
        <meshBasicMaterial color="#1a2030" transparent opacity={bodyOpacity} />
      </mesh>
      <mesh position={[0.7, 0.16, 0]}>
        <boxGeometry args={[0.08, 0.12, 0.66]} />
        <meshBasicMaterial color="#1a2030" transparent opacity={bodyOpacity} />
      </mesh>
      <mesh position={[-0.72, 0.22, 0]}>
        <boxGeometry args={[0.04, 0.1, 0.28]} />
        <meshBasicMaterial color="#0e1218" transparent opacity={bodyOpacity} />
      </mesh>

      {/* Headlights aim local −X (forward). Cone default is +Y → rotate onto −X. */}
      {([-1, 1] as const).map((side) => (
        <group key={`hl-${side}`} position={[-0.72, 0.24, side * 0.2]}>
          <mesh>
            <boxGeometry args={[0.08, 0.09, 0.11]} />
            <meshBasicMaterial color="#fff6c8" transparent opacity={bodyOpacity} toneMapped={false} />
          </mesh>
          <mesh position={[-0.55, -0.08, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <coneGeometry args={[0.22, 1.15, 10, 1, true]} />
            <meshBasicMaterial
              color="#ffe9a0"
              transparent
              opacity={0.16 * bodyOpacity}
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
        </group>
      ))}
      {castHeadlight && bodyOpacity > 0.4 && (
        <pointLight position={[-1.2, 0.2, 0]} intensity={1.6 * bodyOpacity} distance={6} color="#ffe9a0" decay={2} />
      )}

      {([-1, 1] as const).map((side) => (
        <mesh key={`tl-${side}`} position={[0.72, 0.24, side * 0.22]}>
          <boxGeometry args={[0.05, 0.07, 0.1]} />
          <meshBasicMaterial color="#ff2a6d" transparent opacity={bodyOpacity} toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[0.05, 0.58, 0]}>
        <boxGeometry args={[0.35, 0.03, 0.12]} />
        <meshBasicMaterial color={accent} transparent opacity={bodyOpacity} toneMapped={false} />
      </mesh>

      {(
        [
          [-0.42, 0.11, 0.34],
          [-0.42, 0.11, -0.34],
          [0.42, 0.11, 0.34],
          [0.42, 0.11, -0.34],
        ] as const
      ).map((p, i) => (
        <group
          key={i}
          position={p}
          ref={(el) => {
            wheelRefs.current[i] = el
          }}
        >
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.12, 0.12, 0.1, 12]} />
            <meshBasicMaterial color="#0a0c10" transparent opacity={bodyOpacity} />
          </mesh>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.06, 0.06, 0.11, 8]} />
            <meshBasicMaterial color="#8a93a8" transparent opacity={bodyOpacity} />
          </mesh>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.03, 0.03, 0.12, 6]} />
            <meshBasicMaterial color={accent} transparent opacity={bodyOpacity} toneMapped={false} />
          </mesh>
        </group>
      ))}

      {passengers.map((p, i) => (
        <group key={i} position={p.seat} scale={0.2} rotation={[0, -Math.PI / 2, 0]}>
          <BotFigure pose={p.pose} seated />
        </group>
      ))}
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
  { color: '#ff2a6d', accent: '#ff6b9d', occupancy: 'family' as const },
  { color: '#2de2e6', accent: '#7ef9ff', occupancy: 'couple' as const },
  { color: '#f9c80e', accent: '#ffe08a', occupancy: 'driver' as const },
  { color: '#b967ff', accent: '#d4a0ff', occupancy: 'couple' as const },
  { color: '#39ff14', accent: '#9dff9a', occupancy: 'driver' as const },
]

const LANE = 0.72
/** Nose-to-tail gap along the avenue (car length ≈ 1.35). */
const MIN_GAP = 3.6
const ROAD_END = BACK_ROAD_HALF_LEN - 1.2
const FADE_DIST = 2.8

function makeCar(slot: number, dir: -1 | 1, x: number, gen: number): TrafficCar {
  const pal = PALETTE[(slot + gen) % PALETTE.length]
  return {
    slot,
    dir,
    x,
    speed: 2.2 + (slot % 2) * 0.25,
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
 * Exactly 4 cars on the elevated back avenue, right-hand lanes, looping with fade.
 * Same-lane cars keep a hard MIN_GAP so they never intersect.
 */
export function AvenueTraffic({ deckY = 1.35 }: { deckY?: number }) {
  // Two per lane, seeded far apart.
  const sim = useRef<TrafficCar[]>([
    makeCar(0, -1, 10, 0),
    makeCar(1, -1, -6, 0),
    makeCar(2, 1, -12, 0),
    makeCar(3, 1, 4, 0),
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
          c.speed = 2.0 + Math.random() * 0.55
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
        return (
          <CityCar
            key={c.slot}
            position={[c.x, deckY, z]}
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
