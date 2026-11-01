import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

const RAIL_R = 12.4
const RAIL_Y = 0.16
const Z_OFF = -1
/** Distance between inner and outer rail centers (gauge) — wide enough to read from the plaza cam. */
export const RAIL_GAUGE = 0.85
const TIE_COUNT = 80
const SEGMENTS = 160

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function CarBody({
  offset,
  color,
  loco = false,
}: {
  offset: number
  color: string
  loco?: boolean
}) {
  const len = loco ? 1.35 : 1.15
  const half = len / 2
  return (
    <group position={[offset, 0, 0]}>
      {/* Chassis / underframe */}
      <mesh position={[0, 0.12, 0]} castShadow>
        <boxGeometry args={[len, 0.12, 0.62]} />
        <meshStandardMaterial color="#12161e" metalness={0.55} roughness={0.4} />
      </mesh>
      {/* Body */}
      <mesh position={[0, 0.4, 0]} castShadow>
        <boxGeometry args={[len - 0.08, 0.48, 0.56]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.35}
          metalness={0.4}
          roughness={0.35}
        />
      </mesh>
      {/* Roof */}
      <mesh position={[loco ? 0.18 : 0, 0.68, 0]}>
        <boxGeometry args={[loco ? 0.62 : len - 0.2, 0.14, 0.5]} />
        <meshStandardMaterial color="#0a0e18" metalness={0.35} roughness={0.5} />
      </mesh>
      {/* Roof light strip */}
      <mesh position={[0, 0.78, 0]}>
        <boxGeometry args={[len - 0.35, 0.04, 0.16]} />
        <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
      </mesh>
      {/* Side windows */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[loco ? 0.18 : 0, 0.44, side * 0.29]}>
          <boxGeometry args={[loco ? 0.48 : len - 0.35, 0.16, 0.03]} />
          <meshBasicMaterial color="#c8f7ff" transparent opacity={0.9} toneMapped={false} />
        </mesh>
      ))}
      {loco && (
        <>
          {/* Nose */}
          <mesh position={[-half + 0.12, 0.28, 0]} castShadow>
            <boxGeometry args={[0.36, 0.28, 0.52]} />
            <meshStandardMaterial
              color="#f9c80e"
              emissive="#f9c80e"
              emissiveIntensity={0.45}
              metalness={0.45}
              roughness={0.3}
            />
          </mesh>
          {/* Cowcatcher */}
          <mesh position={[-half - 0.05, 0.1, 0]} rotation={[0, 0, -0.4]}>
            <boxGeometry args={[0.22, 0.08, 0.58]} />
            <meshStandardMaterial color="#2a2430" metalness={0.5} roughness={0.45} />
          </mesh>
          {/* Headlight */}
          <mesh position={[-half - 0.08, 0.36, 0]}>
            <sphereGeometry args={[0.08, 12, 12]} />
            <meshBasicMaterial color="#fff8d8" toneMapped={false} />
          </mesh>
          <pointLight position={[-half - 0.25, 0.38, 0]} intensity={1.8} distance={6} color="#ffe9a0" />
          {/* Cab marker */}
          <mesh position={[0.35, 0.8, 0]}>
            <boxGeometry args={[0.2, 0.05, 0.14]} />
            <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
          </mesh>
        </>
      )}
      {/* Wheels on dual rails */}
      {([-half + 0.25, half - 0.25] as const).map((x) =>
        ([-RAIL_GAUGE / 2, RAIL_GAUGE / 2] as const).map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 0.09, z]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.1, 0.1, 0.07, 12]} />
            <meshStandardMaterial color="#1a1e28" metalness={0.75} roughness={0.3} />
          </mesh>
        )),
      )}
      {/* Coupler */}
      <mesh position={[half + 0.02, 0.16, 0]}>
        <boxGeometry args={[0.1, 0.06, 0.06]} />
        <meshStandardMaterial color="#3a4050" metalness={0.6} roughness={0.4} />
      </mesh>
    </group>
  )
}

/** Locomotive + cars that orbit the plaza railroad forever. */
export function PlazaTrain({
  radius = RAIL_R,
  y = RAIL_Y,
  speed = 0.22,
}: {
  radius?: number
  y?: number
  speed?: number
}) {
  const group = useRef<Group>(null)
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const angle = useRef(0)

  useFrame((_, dt) => {
    if (!group.current || reduced) return
    angle.current = (angle.current + dt * speed) % (Math.PI * 2)
    const a = angle.current
    group.current.position.set(Math.cos(a) * radius, y, Math.sin(a) * radius + Z_OFF)
    group.current.rotation.y = -a + Math.PI / 2
  })

  const a0 = 0.35
  const rest: [number, number, number] = [
    Math.cos(a0) * radius,
    y,
    Math.sin(a0) * radius + Z_OFF,
  ]

  return (
    <group ref={group} position={rest} rotation={[0, -a0 + Math.PI / 2, 0]} raycast={() => null}>
      <CarBody offset={0} color="#ff2a6d" loco />
      <CarBody offset={1.4} color="#2de2e6" />
      <CarBody offset={2.7} color="#b967ff" />
      <CarBody offset={4.0} color="#39ff14" />
    </group>
  )
}

/** Wooden sleepers + dual steel rails + ballast — classic circular railroad. */
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

  const signals = useMemo(() => {
    const out: [number, number, number, number][] = []
    const n = 12
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
      {/* Ballast embankment — dark gravel band */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.02, Z_OFF]} receiveShadow>
        <ringGeometry args={[radius - 0.85, radius + 0.85, SEGMENTS]} />
        <meshStandardMaterial color="#14101c" roughness={0.95} metalness={0.04} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.005, Z_OFF]}>
        <ringGeometry args={[radius - 0.65, radius + 0.65, SEGMENTS]} />
        <meshStandardMaterial color="#2a2234" roughness={0.9} metalness={0.06} />
      </mesh>

      {/* Sleepers / ties — radial across the gauge, warm wood so they read from high cam */}
      {ties.map((t, i) => (
        <mesh
          key={i}
          position={[t.x, y + 0.035, t.z]}
          rotation={[0, t.rot, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[1.15, 0.08, 0.22]} />
          <meshStandardMaterial
            color="#5a3a1e"
            emissive="#3a2210"
            emissiveIntensity={0.25}
            roughness={0.9}
            metalness={0.04}
          />
        </mesh>
      ))}

      {/* Dual rails at the same height (classic railroad, not stacked monorail) */}
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.055, 10, SEGMENTS]} />
        <meshStandardMaterial
          color="#d8e4f4"
          emissive="#2de2e6"
          emissiveIntensity={0.35}
          metalness={0.9}
          roughness={0.22}
        />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.055, 10, SEGMENTS]} />
        <meshStandardMaterial
          color="#d8e4f4"
          emissive="#2de2e6"
          emissiveIntensity={0.35}
          metalness={0.9}
          roughness={0.22}
        />
      </mesh>

      {/* Soft neon wash under the rails */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.028, Z_OFF]}>
        <ringGeometry args={[innerR - 0.12, outerR + 0.12, 96]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.18} depthWrite={false} />
      </mesh>

      {/* Trackside signal posts */}
      {signals.map(([x, , z, rot], i) => (
        <group key={i} position={[x, 0, z]} rotation={[0, rot, 0]} raycast={() => null}>
          <mesh position={[0, 0.4, 0]}>
            <cylinderGeometry args={[0.035, 0.045, 0.8, 8]} />
            <meshStandardMaterial color="#1a2438" metalness={0.55} roughness={0.4} />
          </mesh>
          <mesh position={[0, 0.84, 0]}>
            <boxGeometry args={[0.12, 0.16, 0.07]} />
            <meshStandardMaterial color="#101820" metalness={0.4} roughness={0.45} />
          </mesh>
          <mesh position={[0, 0.86, 0.05]}>
            <sphereGeometry args={[0.045, 10, 10]} />
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
