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

/** Arc length between car centers. Lead and tail noses stick out past the body. */
const CAR_ARCS = [0, 2.9, 4.95, 6.95] as const
const STRIPES = ['#f9c80e', '#2de2e6', '#b967ff', '#ff2a6d'] as const
const ROLES = ['lead', 'mid', 'mid', 'tail'] as const
/** Clearance between the skid and the guideway. */
const HOVER = 0.58

function BulletCar({ stripe, role }: { stripe: string; role: 'lead' | 'mid' | 'tail' }) {
  const len = role === 'mid' ? 1.85 : 1.7
  const half = len / 2
  const nose = role === 'lead' || role === 'tail'
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <planeGeometry args={[len * 0.96, 1.05]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.4} depthWrite={false} toneMapped={false} />
      </mesh>
      {([-RAIL_GAUGE / 2, RAIL_GAUGE / 2] as const).map((z) => (
        <mesh key={z} position={[0, 0.08, z]}>
          <boxGeometry args={[len * 0.78, 0.05, 0.08]} />
          <meshBasicMaterial color="#141820" />
        </mesh>
      ))}
      <mesh position={[0, 0.22, 0]}>
        <boxGeometry args={[len, 0.12, 0.66]} />
        <meshStandardMaterial color="#12141c" metalness={0.7} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.46, 0]}>
        <boxGeometry args={[len - 0.06, 0.36, 0.6]} />
        <meshStandardMaterial color="#f4f0d4" metalness={0.28} roughness={0.42} />
      </mesh>
      <mesh position={[0, 0.66, 0]}>
        <boxGeometry args={[len - 0.1, 0.06, 0.48]} />
        <meshStandardMaterial color="#f4f0d4" metalness={0.22} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.7, 0]}>
        <boxGeometry args={[len * 0.72, 0.025, 0.07]} />
        <meshBasicMaterial color={stripe} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.3, 0]}>
        <boxGeometry args={[len + 0.02, 0.055, 0.64]} />
        <meshBasicMaterial color={stripe} toneMapped={false} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[role === 'lead' ? 0.12 : 0, 0.5, side * 0.31]}>
          <boxGeometry args={[role === 'mid' ? len - 0.28 : len - 0.42, 0.12, 0.03]} />
          <meshBasicMaterial color="#9fdfff" transparent opacity={0.85} toneMapped={false} />
        </mesh>
      ))}
      {nose && role === 'lead' && (
        <mesh position={[-half - 0.42, 0.4, 0]} rotation={[0, 0, Math.PI / 2]}>
          <coneGeometry args={[0.26, 1.05, 10]} />
          <meshStandardMaterial color="#f4f0d4" metalness={0.3} roughness={0.4} />
        </mesh>
      )}
      {nose && role === 'lead' && (
        <mesh position={[-half - 0.9, 0.4, 0]}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshBasicMaterial color="#fff6c8" toneMapped={false} />
        </mesh>
      )}
      {nose && role === 'tail' && (
        <mesh position={[half + 0.36, 0.4, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <coneGeometry args={[0.24, 0.85, 10]} />
          <meshStandardMaterial color="#f4f0d4" metalness={0.3} roughness={0.4} />
        </mesh>
      )}
      {nose && role === 'tail' && (
        <mesh position={[half + 0.74, 0.42, 0]}>
          <boxGeometry args={[0.06, 0.08, 0.16]} />
          <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
        </mesh>
      )}
    </group>
  )
}

/** Maglev bullet train. Same loop, held above the guideway. Forward is local −X. */
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
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const angle = useRef(0.35)

  useFrame(({ clock }, dt) => {
    if (reduced) return
    angle.current = (angle.current + dt * speed) % (Math.PI * 2)
    const a0 = angle.current
    const hoverY = y + HOVER + Math.sin(clock.getElapsedTime() * 1.5) * 0.03
    for (let i = 0; i < CAR_ARCS.length; i++) {
      const g = carRefs.current[i]
      if (!g) continue
      const a = a0 - CAR_ARCS[i] / radius
      g.position.set(Math.cos(a) * radius, hoverY, Math.sin(a) * radius + Z_OFF)
      g.rotation.y = -a + Math.PI / 2
    }
  })

  return (
    <group raycast={() => null}>
      {CAR_ARCS.map((arc, i) => {
        const a = 0.35 - arc / radius
        return (
          <group
            key={i}
            ref={(el) => {
              carRefs.current[i] = el
            }}
            position={[Math.cos(a) * radius, y + HOVER, Math.sin(a) * radius + Z_OFF]}
            rotation={[0, -a + Math.PI / 2, 0]}
          >
            <BulletCar stripe={STRIPES[i]} role={ROLES[i]} />
          </group>
        )
      })}
    </group>
  )
}

/** Maglev guideway on the same loop — dark beam, neon rails, no wooden ties. */
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

      {/* Twin guide rails — cyan inside, gold outside */}
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#d8fbff" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#ffe08a" toneMapped={false} />
      </mesh>

      {/* Fishplates / joint hardware */}
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
        </group>
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.028, Z_OFF]}>
        <ringGeometry args={[innerR - 0.12, outerR + 0.12, 48]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.16} depthWrite={false} />
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
            <meshBasicMaterial
              color={i % 3 === 0 ? '#39ff14' : i % 3 === 1 ? '#f9c80e' : '#ff2a6d'}
              toneMapped={false}
            />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export { RAIL_GAUGE }
