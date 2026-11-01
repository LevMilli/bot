import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

const RAIL_R = 12.4
const RAIL_Y = 0.42
const Z_OFF = -1

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Neon monorail car that orbits the plaza rail forever. */
export function PlazaTrain({
  radius = RAIL_R,
  y = RAIL_Y,
  speed = 0.18,
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

  // Park the train on the rail when motion is reduced.
  const a0 = 0.35
  const rest: [number, number, number] = [
    Math.cos(a0) * radius,
    y,
    Math.sin(a0) * radius + Z_OFF,
  ]

  return (
    <group ref={group} position={rest} rotation={[0, -a0 + Math.PI / 2, 0]} raycast={() => null}>
      {/* chassis */}
      <mesh position={[0, 0.08, 0]} castShadow>
        <boxGeometry args={[1.35, 0.28, 0.42]} />
        <meshStandardMaterial color="#0a1220" metalness={0.55} roughness={0.28} emissive="#123a55" emissiveIntensity={0.35} />
      </mesh>
      {/* nose */}
      <mesh position={[0.72, 0.08, 0]}>
        <boxGeometry args={[0.28, 0.22, 0.36]} />
        <meshStandardMaterial color="#101828" metalness={0.5} roughness={0.3} />
      </mesh>
      {/* roof light strip */}
      <mesh position={[0, 0.24, 0]}>
        <boxGeometry args={[1.1, 0.04, 0.18]} />
        <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
      </mesh>
      {/* side windows */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[0.05, 0.12, side * 0.21]}>
          <boxGeometry args={[0.9, 0.12, 0.02]} />
          <meshBasicMaterial color="#2de2e6" transparent opacity={0.85} toneMapped={false} />
        </mesh>
      ))}
      {/* headlight */}
      <mesh position={[0.88, 0.08, 0]}>
        <sphereGeometry args={[0.06, 12, 12]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      <pointLight position={[0.95, 0.1, 0]} intensity={1.4} color="#7ef9ff" distance={4} />
      {/* bogies */}
      {([-0.4, 0.35] as const).map((x) => (
        <mesh key={x} position={[x, -0.02, 0]}>
          <boxGeometry args={[0.22, 0.08, 0.48]} />
          <meshStandardMaterial color="#1a2438" metalness={0.6} roughness={0.35} />
        </mesh>
      ))}
      {/* trailing glow car */}
      <mesh position={[-0.95, 0.06, 0]}>
        <boxGeometry args={[0.55, 0.2, 0.32]} />
        <meshStandardMaterial color="#0c1018" emissive="#ff2a6d" emissiveIntensity={0.45} metalness={0.4} roughness={0.4} />
      </mesh>
    </group>
  )
}

/** Vertical posts under the elevated double rail. */
export function RailPosts({
  radius = RAIL_R,
  count = 24,
  y = 0.28,
}: {
  radius?: number
  count?: number
  y?: number
}) {
  const posts = useMemo(() => {
    const out: [number, number, number][] = []
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2
      out.push([Math.cos(a) * radius, y / 2, Math.sin(a) * radius + Z_OFF])
    }
    return out
  }, [radius, count, y])

  return (
    <group raycast={() => null}>
      {posts.map((p, i) => (
        <group key={i} position={p}>
          <mesh>
            <cylinderGeometry args={[0.035, 0.045, y, 8]} />
            <meshStandardMaterial color="#1a3048" metalness={0.55} roughness={0.4} />
          </mesh>
          <mesh position={[0, y / 2 + 0.02, 0]}>
            <boxGeometry args={[0.12, 0.04, 0.12]} />
            <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
          </mesh>
        </group>
      ))}
    </group>
  )
}
