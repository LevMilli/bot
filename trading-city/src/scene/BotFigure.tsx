import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

/** Synthwave office bot — round head, ear rings, raised arms. */
export function BotFigure({ celebrating = true }: { celebrating?: boolean }) {
  const armL = useRef<Group>(null)
  const armR = useRef<Group>(null)
  const body = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const lift = celebrating ? 1.25 + Math.sin(t * 2.2) * 0.08 : 0.35
    if (armL.current) {
      armL.current.rotation.z = lift
      armL.current.rotation.x = -0.2
    }
    if (armR.current) {
      armR.current.rotation.z = -lift
      armR.current.rotation.x = -0.2
    }
    if (body.current) body.current.position.y = 0.02 + Math.sin(t * 1.6) * 0.015
  })

  return (
    <group ref={body} position={[0, 0.95, 0.55]}>
      {/* torso */}
      <mesh position={[0, 0.45, 0]}>
        <capsuleGeometry args={[0.32, 0.42, 6, 14]} />
        <meshStandardMaterial color="#5ad8ff" emissive="#1a8cff" emissiveIntensity={0.45} roughness={0.35} />
      </mesh>
      {/* head */}
      <mesh position={[0, 1.18, 0]}>
        <sphereGeometry args={[0.36, 24, 24]} />
        <meshStandardMaterial color="#7ae8ff" emissive="#2de2e6" emissiveIntensity={0.3} roughness={0.3} />
      </mesh>
      {/* antenna */}
      <mesh position={[0, 1.55, 0]}>
        <cylinderGeometry args={[0.025, 0.025, 0.22, 8]} />
        <meshBasicMaterial color="#c8f7ff" />
      </mesh>
      <mesh position={[0, 1.68, 0]}>
        <sphereGeometry args={[0.05, 10, 10]} />
        <meshBasicMaterial color="#39ff14" />
      </mesh>
      {/* ear / headphone rings */}
      {([-0.34, 0.34] as const).map((x) => (
        <group key={x} position={[x, 1.18, 0]} rotation={[0, 0, x > 0 ? -0.2 : 0.2]}>
          <mesh rotation={[0, Math.PI / 2, 0]}>
            <torusGeometry args={[0.12, 0.035, 10, 20]} />
            <meshBasicMaterial color="#39ff14" />
          </mesh>
          <mesh position={[x > 0 ? 0.02 : -0.02, 0, 0]}>
            <sphereGeometry args={[0.07, 12, 12]} />
            <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.4} />
          </mesh>
        </group>
      ))}
      {/* arms */}
      <group ref={armL} position={[-0.4, 0.7, 0]}>
        <mesh position={[0, -0.32, 0]}>
          <capsuleGeometry args={[0.09, 0.38, 4, 10]} />
          <meshStandardMaterial color="#5ad8ff" />
        </mesh>
        <mesh position={[0, -0.58, 0]}>
          <sphereGeometry args={[0.1, 10, 10]} />
          <meshStandardMaterial color="#9aecff" emissive="#ff9a3c" emissiveIntensity={0.6} />
        </mesh>
      </group>
      <group ref={armR} position={[0.4, 0.7, 0]}>
        <mesh position={[0, -0.32, 0]}>
          <capsuleGeometry args={[0.09, 0.38, 4, 10]} />
          <meshStandardMaterial color="#5ad8ff" />
        </mesh>
        <mesh position={[0, -0.58, 0]}>
          <sphereGeometry args={[0.1, 10, 10]} />
          <meshStandardMaterial color="#9aecff" emissive="#ff9a3c" emissiveIntensity={0.6} />
        </mesh>
      </group>
      {/* legs tucked on chair */}
      <mesh position={[-0.14, 0.02, 0.05]} rotation={[0.4, 0, 0]}>
        <capsuleGeometry args={[0.09, 0.28, 4, 8]} />
        <meshStandardMaterial color="#3a9ec8" />
      </mesh>
      <mesh position={[0.14, 0.02, 0.05]} rotation={[0.4, 0, 0]}>
        <capsuleGeometry args={[0.09, 0.28, 4, 8]} />
        <meshStandardMaterial color="#3a9ec8" />
      </mesh>
    </group>
  )
}
