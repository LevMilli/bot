import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

/** Synthwave office bot — pale cyan body, ear disks, back-panel cross, raised arms. */
export function BotFigure({ celebrating = true }: { celebrating?: boolean }) {
  const armL = useRef<Group>(null)
  const armR = useRef<Group>(null)
  const body = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const lift = celebrating ? 1.32 + Math.sin(t * 2.2) * 0.07 : 0.35
    if (armL.current) {
      armL.current.rotation.z = lift
      armL.current.rotation.x = -0.15
    }
    if (armR.current) {
      armR.current.rotation.z = -lift
      armR.current.rotation.x = -0.15
    }
    if (body.current) body.current.position.y = 0.02 + Math.sin(t * 1.6) * 0.012
  })

  return (
    <group ref={body} position={[0, 0.95, 0.55]}>
      {/* torso */}
      <mesh position={[0, 0.45, 0]}>
        <capsuleGeometry args={[0.34, 0.48, 6, 16]} />
        <meshStandardMaterial
          color="#6adfff"
          emissive="#1a8cff"
          emissiveIntensity={0.35}
          roughness={0.28}
          metalness={0.15}
        />
      </mesh>

      {/* black back panel + white cross + green bars (ref) */}
      <mesh position={[0, 0.48, -0.3]}>
        <boxGeometry args={[0.52, 0.72, 0.06]} />
        <meshStandardMaterial color="#050508" roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.5, -0.34]}>
        <boxGeometry args={[0.1, 0.55, 0.04]} />
        <meshBasicMaterial color="#f4f7ff" />
      </mesh>
      <mesh position={[0, 0.62, -0.34]}>
        <boxGeometry args={[0.28, 0.1, 0.04]} />
        <meshBasicMaterial color="#f4f7ff" />
      </mesh>
      <mesh position={[-0.16, 0.48, -0.34]}>
        <boxGeometry args={[0.05, 0.42, 0.035]} />
        <meshBasicMaterial color="#39ff14" />
      </mesh>
      <mesh position={[0.16, 0.48, -0.34]}>
        <boxGeometry args={[0.05, 0.42, 0.035]} />
        <meshBasicMaterial color="#39ff14" />
      </mesh>

      {/* head */}
      <mesh position={[0, 1.22, 0]}>
        <sphereGeometry args={[0.38, 28, 28]} />
        <meshStandardMaterial
          color="#8aeeff"
          emissive="#2de2e6"
          emissiveIntensity={0.28}
          roughness={0.25}
          metalness={0.12}
        />
      </mesh>
      {/* antenna + yellow bulb */}
      <mesh position={[0, 1.6, 0]}>
        <cylinderGeometry args={[0.022, 0.022, 0.26, 8]} />
        <meshBasicMaterial color="#c8f7ff" />
      </mesh>
      <mesh position={[0, 1.76, 0]}>
        <sphereGeometry args={[0.055, 12, 12]} />
        <meshBasicMaterial color="#f9c80e" />
      </mesh>
      {/* ear / headphone disks */}
      {([-0.36, 0.36] as const).map((x) => (
        <group key={x} position={[x, 1.22, 0]} rotation={[0, 0, x > 0 ? -0.15 : 0.15]}>
          <mesh rotation={[0, Math.PI / 2, 0]}>
            <torusGeometry args={[0.13, 0.032, 10, 24]} />
            <meshBasicMaterial color="#39ff14" />
          </mesh>
          <mesh position={[x > 0 ? 0.03 : -0.03, 0, 0]}>
            <sphereGeometry args={[0.085, 14, 14]} />
            <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.6} />
          </mesh>
        </group>
      ))}
      {/* arms */}
      <group ref={armL} position={[-0.42, 0.72, 0]}>
        <mesh position={[0, -0.34, 0]}>
          <capsuleGeometry args={[0.095, 0.4, 4, 10]} />
          <meshStandardMaterial color="#5ad8ff" roughness={0.3} />
        </mesh>
        <mesh position={[0, -0.62, 0]}>
          <sphereGeometry args={[0.11, 12, 12]} />
          <meshStandardMaterial color="#d8f7ff" emissive="#ffffff" emissiveIntensity={0.55} />
        </mesh>
      </group>
      <group ref={armR} position={[0.42, 0.72, 0]}>
        <mesh position={[0, -0.34, 0]}>
          <capsuleGeometry args={[0.095, 0.4, 4, 10]} />
          <meshStandardMaterial color="#5ad8ff" roughness={0.3} />
        </mesh>
        <mesh position={[0, -0.62, 0]}>
          <sphereGeometry args={[0.11, 12, 12]} />
          <meshStandardMaterial color="#d8f7ff" emissive="#ffffff" emissiveIntensity={0.55} />
        </mesh>
      </group>
      {/* legs tucked on chair */}
      <mesh position={[-0.15, 0.02, 0.08]} rotation={[0.45, 0, 0.08]}>
        <capsuleGeometry args={[0.095, 0.3, 4, 8]} />
        <meshStandardMaterial color="#3a9ec8" />
      </mesh>
      <mesh position={[0.15, 0.02, 0.08]} rotation={[0.45, 0, -0.08]}>
        <capsuleGeometry args={[0.095, 0.3, 4, 8]} />
        <meshStandardMaterial color="#3a9ec8" />
      </mesh>
    </group>
  )
}
