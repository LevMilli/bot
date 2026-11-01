import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, MeshStandardMaterial } from 'three'

const SKIN = '#9af4ff'

function skinMaterial(emissiveIntensity = 0.28) {
  return {
    color: SKIN,
    emissive: '#1496c8',
    emissiveIntensity,
    roughness: 0.32,
    metalness: 0.22,
  }
}

/** Three-prong gripper, matching the raised-arm reference bot. */
function Grip() {
  return (
    <group position={[0, 0.06, 0]}>
      {([-0.62, 0, 0.62] as const).map((spread) => (
        <mesh key={spread} position={[spread * 0.1, 0.08, 0]} rotation={[0.2, 0, spread * 0.45]}>
          <boxGeometry args={[0.03, 0.16, 0.03]} />
          <meshStandardMaterial {...skinMaterial(0.45)} />
        </mesh>
      ))}
    </group>
  )
}

function Arm({ side, celebrating }: { side: -1 | 1; celebrating: boolean }) {
  const ref = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const lift = celebrating ? Math.sin(t * 2.05 + side) * 0.045 : Math.sin(t * 0.8) * 0.02
    if (!ref.current) return
    // Built along +Y. Positive Z spin swings +Y toward screen-left (camera looks from +Z).
    ref.current.rotation.z = -side * 1.05 + -side * lift
    ref.current.rotation.x = -0.38
  })

  return (
    <group ref={ref} position={[side * 0.46, 0.98, 0]} rotation={[-0.38, 0, -side * 1.05]}>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.075, 0.085, 0.38, 14]} />
        <meshStandardMaterial {...skinMaterial(0.32)} />
      </mesh>
      <mesh position={[0, 0.4, 0]}>
        <sphereGeometry args={[0.09, 14, 14]} />
        <meshStandardMaterial color="#14506c" emissive="#1a8cff" emissiveIntensity={0.2} roughness={0.35} metalness={0.4} />
      </mesh>
      <mesh position={[0, 0.4, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.095, 0.016, 8, 18]} />
        <meshStandardMaterial color="#0c3044" metalness={0.5} roughness={0.35} />
      </mesh>
      <group position={[0, 0.4, 0]} rotation={[-0.42, 0, side * 0.12]}>
        <mesh position={[0, 0.2, 0]}>
          <cylinderGeometry args={[0.06, 0.072, 0.38, 14]} />
          <meshStandardMaterial {...skinMaterial(0.32)} />
        </mesh>
        <mesh position={[0, 0.4, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.075, 0.014, 8, 16]} />
          <meshBasicMaterial color="#e8fbff" toneMapped={false} />
        </mesh>
        <group position={[0, 0.48, 0]}>
          <Grip />
        </group>
      </group>
    </group>
  )
}

/**
 * Desk bot seen from behind: dome helmet, yellow ear disks, antenna bulb,
 * black back panel with a white cross and green side bars, arms in a V.
 */
export function BotFigure({ celebrating = true }: { celebrating?: boolean }) {
  const body = useRef<Group>(null)
  const bulb = useRef<MeshStandardMaterial>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (body.current) body.current.position.y = Math.sin(t * 1.5) * 0.012
    if (bulb.current) bulb.current.emissiveIntensity = 1.4 + Math.sin(t * 3.2) * 0.35
  })

  return (
    <group ref={body} position={[0, 0.55, 0.42]}>
      <mesh position={[0, 0.14, 0]}>
        <sphereGeometry args={[0.22, 18, 14]} />
        <meshStandardMaterial {...skinMaterial(0.2)} />
      </mesh>
      <mesh position={[0, 0.52, 0]}>
        <cylinderGeometry args={[0.3, 0.34, 0.58, 20]} />
        <meshStandardMaterial {...skinMaterial(0.22)} />
      </mesh>
      <mesh position={[0, 0.84, 0]} rotation={[0, 0, Math.PI / 2]}>
        <capsuleGeometry args={[0.11, 0.46, 6, 12]} />
        <meshStandardMaterial {...skinMaterial(0.3)} />
      </mesh>

      {/* Back panel faces the camera (+Z). Short pack; helmet sits clear above it. */}
      <mesh position={[0, 0.42, 0.42]}>
        <boxGeometry args={[0.5, 0.62, 0.06]} />
        <meshStandardMaterial color="#07080d" roughness={0.5} metalness={0.25} />
      </mesh>
      <mesh position={[0, 0.44, 0.48]}>
        <boxGeometry args={[0.08, 0.42, 0.025]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.58, 0.48]}>
        <boxGeometry args={[0.26, 0.07, 0.025]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {([-0.16, 0.16] as const).map((x) => (
        <mesh key={x} position={[x, 0.42, 0.48]}>
          <boxGeometry args={[0.04, 0.4, 0.02]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[0, 0.95, 0.08]}>
        <cylinderGeometry args={[0.09, 0.12, 0.12, 12]} />
        <meshStandardMaterial {...skinMaterial(0.25)} />
      </mesh>
      <mesh position={[0, 1.22, 0.12]}>
        <sphereGeometry args={[0.3, 28, 18]} />
        <meshStandardMaterial color="#d7fdff" emissive="#7ae8ff" emissiveIntensity={0.5} roughness={0.2} metalness={0.25} />
      </mesh>
      <mesh position={[0, 1.16, -0.1]} rotation={[0.4, 0, 0]}>
        <boxGeometry args={[0.26, 0.07, 0.04]} />
        <meshStandardMaterial color="#041018" metalness={0.65} roughness={0.25} />
      </mesh>

      <mesh position={[0, 1.56, 0.12]}>
        <cylinderGeometry args={[0.015, 0.015, 0.16, 8]} />
        <meshBasicMaterial color="#e7fdff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.68, 0.12]}>
        <sphereGeometry args={[0.048, 14, 14]} />
        <meshStandardMaterial ref={bulb} color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.6} roughness={0.25} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <group key={side} position={[side * 0.32, 1.22, 0.16]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.09, 0.09, 0.045, 18]} />
            <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={0.85} roughness={0.3} />
          </mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.09, 0.014, 8, 18]} />
            <meshBasicMaterial color="#39ff14" toneMapped={false} />
          </mesh>
        </group>
      ))}

      <Arm side={-1} celebrating={celebrating} />
      <Arm side={1} celebrating={celebrating} />

      {([-0.14, 0.14] as const).map((x) => (
        <mesh key={x} position={[x, -0.02, 0.08]} rotation={[0.7, 0, x > 0 ? -0.08 : 0.08]}>
          <cylinderGeometry args={[0.08, 0.075, 0.36, 12]} />
          <meshStandardMaterial {...skinMaterial(0.15)} />
        </mesh>
      ))}
    </group>
  )
}
