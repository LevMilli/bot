import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'
import { RAIL_GAUGE, RAIL_R, RAIL_Z_OFF } from './plazaLayout'

const RAIL_Y = 0.2
const Z_OFF = RAIL_Z_OFF
const TIE_COUNT = 36
const SEGMENTS = 56

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** One purple livery. Bogie spacing keeps both skids on the guideway. */
const CARS = [
  { arc: 0, role: 'lead' as const, len: 2.05 },
  { arc: 2.16, role: 'mid' as const, len: 1.92 },
  { arc: 4.24, role: 'mid' as const, len: 1.92 },
  { arc: 6.32, role: 'tail' as const, len: 1.88 },
]
/** Gap from the rail head to the skid. Each car bobs on its own. */
const HOVER = 0.13

const BODY = '#3a1674'
const BODY_DARK = '#12081c'
const BODY_MID = '#5b2d9e'
const GLOW = '#c084fc'
const GLOW_HOT = '#f3e8ff'
const GLASS = '#0c0614'

function railPoint(angle: number, radius: number) {
  return {
    x: Math.cos(angle) * radius,
    z: Math.sin(angle) * radius + Z_OFF,
  }
}

/**
 * Rigid car whose bogies sit on the loop. The body is the chord between them,
 * so the ends stay over the rails instead of swinging inside the curve.
 * Forward is local −X, toward increasing angle.
 */
function poseOnRail(angle: number, radius: number, bogie: number) {
  const da = bogie / radius
  const front = railPoint(angle + da, radius)
  const rear = railPoint(angle - da, radius)
  const dx = front.x - rear.x
  const dz = front.z - rear.z
  return {
    x: (front.x + rear.x) / 2,
    z: (front.z + rear.z) / 2,
    rotY: Math.atan2(dz, -dx),
  }
}

function BulletCar({ role, len }: { role: 'lead' | 'mid' | 'tail'; len: number }) {
  const half = len / 2
  const panes = role === 'mid' ? [-0.34, -0.08, 0.18, 0.44] : [-0.22, 0.08, 0.36]
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <planeGeometry args={[len * 0.94, 1.2]} />
        <meshBasicMaterial color={GLOW} transparent opacity={0.42} depthWrite={false} toneMapped={false} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <group key={side} position={[0, 0.045, side * (RAIL_GAUGE / 2)]}>
          <mesh>
            <boxGeometry args={[len * 0.7, 0.04, 0.11]} />
            <meshStandardMaterial color="#07040e" metalness={0.72} roughness={0.28} />
          </mesh>
          <mesh position={[0, -0.012, 0]}>
            <boxGeometry args={[len * 0.6, 0.016, 0.055]} />
            <meshBasicMaterial color={GLOW} toneMapped={false} />
          </mesh>
          {([-0.32, 0.32] as const).map((at) => (
            <mesh key={at} position={[at * len, 0.028, 0]}>
              <boxGeometry args={[0.18, 0.028, 0.13]} />
              <meshStandardMaterial color={BODY_MID} emissive={GLOW} emissiveIntensity={0.55} roughness={0.35} />
            </mesh>
          ))}
        </group>
      ))}

      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[len, 0.09, 0.72]} />
        <meshStandardMaterial color={BODY_DARK} metalness={0.78} roughness={0.26} />
      </mesh>
      <mesh position={[0, 0.175, 0]}>
        <boxGeometry args={[len + 0.02, 0.04, 0.9]} />
        <meshStandardMaterial color={BODY} metalness={0.5} roughness={0.36} emissive={GLOW} emissiveIntensity={0.12} />
      </mesh>
      <mesh position={[0, 0.36, 0]}>
        <boxGeometry args={[len - 0.02, 0.3, 0.64]} />
        <meshStandardMaterial color={BODY} metalness={0.46} roughness={0.3} emissive="#2a1058" emissiveIntensity={0.28} />
      </mesh>
      <mesh position={[0, 0.53, 0]}>
        <boxGeometry args={[len - 0.1, 0.07, 0.5]} />
        <meshStandardMaterial color={BODY_MID} metalness={0.4} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.59, 0]}>
        <boxGeometry args={[len - 0.18, 0.04, 0.34]} />
        <meshStandardMaterial color={BODY_DARK} metalness={0.55} roughness={0.28} />
      </mesh>
      <mesh position={[0, 0.62, 0]}>
        <boxGeometry args={[len * 0.66, 0.018, 0.055]} />
        <meshBasicMaterial color={GLOW} toneMapped={false} />
      </mesh>

      <mesh position={[0, 0.22, 0]}>
        <boxGeometry args={[len + 0.01, 0.028, 0.8]} />
        <meshBasicMaterial color={GLOW} toneMapped={false} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[role === 'lead' ? 0.1 : 0, 0.4, side * 0.33]}>
            <boxGeometry args={[role === 'mid' ? len - 0.32 : len - 0.52, 0.11, 0.02]} />
            <meshStandardMaterial color={GLASS} metalness={0.82} roughness={0.08} emissive="#b9a0e8" emissiveIntensity={0.4} />
          </mesh>
          {panes.map((at) => (
            <mesh key={at} position={[at * len * 0.7, 0.4, side * 0.342]}>
              <boxGeometry args={[0.018, 0.12, 0.01]} />
              <meshStandardMaterial color={BODY_DARK} />
            </mesh>
          ))}
          {([-0.24, 0.24] as const).map((at) => (
            <mesh key={at} position={[at * len, 0.32, side * 0.345]}>
              <boxGeometry args={[0.016, 0.2, 0.008]} />
              <meshStandardMaterial color="#1a0c28" />
            </mesh>
          ))}
        </group>
      ))}

      {role === 'mid' && (
        <mesh position={[0, 0.66, 0]}>
          <boxGeometry args={[0.42, 0.055, 0.22]} />
          <meshStandardMaterial color={BODY_MID} emissive={GLOW} emissiveIntensity={0.35} roughness={0.4} />
        </mesh>
      )}

      {role === 'lead' && (
        <group>
          <mesh position={[-half - 0.5, 0.34, 0]} rotation={[0, 0, Math.PI / 2]}>
            <coneGeometry args={[0.22, 1.18, 14]} />
            <meshStandardMaterial color={BODY} metalness={0.42} roughness={0.3} emissive="#2a1058" emissiveIntensity={0.22} />
          </mesh>
          <mesh position={[-half - 0.22, 0.44, 0]} rotation={[0, 0, 0.42]}>
            <boxGeometry args={[0.34, 0.07, 0.32]} />
            <meshStandardMaterial color={GLASS} metalness={0.75} roughness={0.1} emissive="#d8c4ff" emissiveIntensity={0.55} />
          </mesh>
          <mesh position={[-half - 1.02, 0.3, 0]}>
            <boxGeometry args={[0.06, 0.05, 0.2]} />
            <meshBasicMaterial color={GLOW_HOT} toneMapped={false} />
          </mesh>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[-half - 0.72, 0.3, side * 0.16]}>
              <boxGeometry args={[0.05, 0.04, 0.05]} />
              <meshBasicMaterial color={GLOW} toneMapped={false} />
            </mesh>
          ))}
        </group>
      )}

      {role === 'tail' && (
        <group>
          <mesh position={[half + 0.36, 0.33, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <coneGeometry args={[0.2, 0.82, 12]} />
            <meshStandardMaterial color={BODY} metalness={0.42} roughness={0.3} emissive="#2a1058" emissiveIntensity={0.16} />
          </mesh>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[half + 0.7, 0.36, side * 0.12]}>
              <boxGeometry args={[0.045, 0.06, 0.07]} />
              <meshBasicMaterial color={GLOW} toneMapped={false} />
            </mesh>
          ))}
        </group>
      )}

      {role !== 'tail' && (
        <mesh position={[half + 0.08, 0.34, 0]}>
          <boxGeometry args={[0.16, 0.2, 0.34]} />
          <meshStandardMaterial color="#1a0c30" roughness={0.62} metalness={0.2} />
        </mesh>
      )}
    </group>
  )
}

/** Purple maglev. Bogies locked to the loop, body hovering just above the rails. */
export function PlazaTrain({
  radius = RAIL_R,
  y = RAIL_Y,
  speed = 0.28,
}: {
  radius?: number
  y?: number
  speed?: number
}) {
  const carRefs = useRef<(Group | null)[]>([])
  const bobRefs = useRef<(Group | null)[]>([])
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const angle = useRef(1.15)

  useFrame(({ clock }, dt) => {
    if (!reduced) angle.current = (angle.current + dt * speed) % (Math.PI * 2)
    const t = clock.getElapsedTime()
    const a0 = angle.current
    for (let i = 0; i < CARS.length; i++) {
      const g = carRefs.current[i]
      if (!g) continue
      const car = CARS[i]
      const a = a0 - car.arc / radius
      const pose = poseOnRail(a, radius, car.len * 0.32)
      g.position.set(pose.x, y, pose.z)
      g.rotation.y = pose.rotY
      const bob = bobRefs.current[i]
      if (!bob) continue
      const lift = reduced
        ? HOVER
        : HOVER + Math.sin(t * 1.65 + i * 1.15) * 0.016 + Math.sin(t * 0.48) * 0.006
      bob.position.y = lift
      bob.rotation.z = car.role === 'lead' ? -0.03 : 0
    }
  })

  return (
    <group raycast={() => null}>
      {CARS.map((car, i) => {
        const a = 1.15 - car.arc / radius
        const pose = poseOnRail(a, radius, car.len * 0.32)
        return (
          <group
            key={car.role + i}
            ref={(el) => {
              carRefs.current[i] = el
            }}
            position={[pose.x, y, pose.z]}
            rotation={[0, pose.rotY, 0]}
          >
            <group
              ref={(el) => {
                bobRefs.current[i] = el
              }}
              position={[0, HOVER, 0]}
            >
              <BulletCar role={car.role} len={car.len} />
            </group>
          </group>
        )
      })}
    </group>
  )
}

/** Maglev guideway on the same loop — dark beam, neon rails, purple center. */
export function PlazaRailroad({
  radius = RAIL_R,
  y = 0.06,
}: {
  radius?: number
  y?: number
}) {
  const ties = useMemo(() => {
    const out: { x: number; z: number; rot: number }[] = []
    for (let i = 0; i < TIE_COUNT; i++) {
      const a = (i / TIE_COUNT) * Math.PI * 2
      out.push({
        x: Math.cos(a) * radius,
        z: Math.sin(a) * radius + Z_OFF,
        rot: -a,
      })
    }
    return out
  }, [radius])

  const plates = useMemo(() => {
    const out: { x: number; z: number; rot: number }[] = []
    const n = 16
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + 0.04
      out.push({
        x: Math.cos(a) * radius,
        z: Math.sin(a) * radius + Z_OFF,
        rot: -a,
      })
    }
    return out
  }, [radius])

  const signals = useMemo(() => {
    const out: [number, number, number, number][] = []
    const n = 6
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2
      const r = radius + 0.95
      out.push([Math.cos(a) * r, 0, Math.sin(a) * r + Z_OFF, -a])
    }
    return out
  }, [radius])

  const innerR = radius - RAIL_GAUGE / 2
  const outerR = radius + RAIL_GAUGE / 2

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.02, Z_OFF]}>
        <ringGeometry args={[radius - 0.9, radius + 0.9, SEGMENTS]} />
        <meshBasicMaterial color="#0c0e14" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.005, Z_OFF]}>
        <ringGeometry args={[radius - 0.68, radius + 0.68, SEGMENTS]} />
        <meshBasicMaterial color="#16141e" />
      </mesh>

      {ties.map((t, i) => (
        <mesh key={i} position={[t.x, y + 0.03, t.z]} rotation={[0, t.rot, 0]}>
          <boxGeometry args={[1.15, 0.05, 0.16]} />
          <meshBasicMaterial color={i % 2 === 0 ? '#1c2030' : '#141820'} />
        </mesh>
      ))}

      {/* Twin guide rails stay cyan / gold. A purple beam is what the train rides. */}
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.08, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius, 0.03, 6, SEGMENTS]} />
        <meshBasicMaterial color="#b967ff" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#d8fbff" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#ffe08a" toneMapped={false} />
      </mesh>

      {plates.map((p, i) => (
        <group key={`pl-${i}`} position={[p.x, y + 0.1, p.z]} rotation={[0, p.rot, 0]}>
          <mesh position={[0, 0.02, -RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.18, 0.05, 0.1]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.05, -RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.08, 0.03, 0.06]} />
            <meshBasicMaterial color="#2de2e6" toneMapped={false} />
          </mesh>
          <mesh position={[0, 0.02, RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.18, 0.05, 0.1]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.05, RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.08, 0.03, 0.06]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          <mesh position={[0, 0.03, 0]}>
            <boxGeometry args={[0.1, 0.025, 0.08]} />
            <meshBasicMaterial color="#b967ff" toneMapped={false} />
          </mesh>
        </group>
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.028, Z_OFF]}>
        <ringGeometry args={[innerR - 0.12, outerR + 0.12, 48]} />
        <meshBasicMaterial color="#b967ff" transparent opacity={0.14} depthWrite={false} />
      </mesh>

      {signals.map(([x, , z, rot], i) => (
        <group key={i} position={[x, 0, z]} rotation={[0, rot, 0]} raycast={() => null}>
          <mesh position={[0, 0.4, 0]}>
            <cylinderGeometry args={[0.035, 0.045, 0.8, 6]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.84, 0]}>
            <boxGeometry args={[0.12, 0.16, 0.07]} />
            <meshBasicMaterial color="#101820" />
          </mesh>
          <mesh position={[0, 0.86, 0.05]}>
            <sphereGeometry args={[0.045, 8, 8]} />
            <meshBasicMaterial color={i % 2 === 0 ? '#c084fc' : '#6d28d9'} toneMapped={false} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export { RAIL_GAUGE }
