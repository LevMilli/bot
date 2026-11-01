import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

/** Synthwave office bot — pale cyan humanoid, ear disks, back-panel cross, raised arms. */
export function BotFigure({ celebrating = true }: { celebrating?: boolean }) {
  const armL = useRef<Group>(null)
  const armR = useRef<Group>(null)
  const body = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const lift = celebrating ? 1.05 + Math.sin(t * 2.2) * 0.06 : 0.35
    if (armL.current) {
      armL.current.rotation.z = lift
      armL.current.rotation.x = -0.35
    }
    if (armR.current) {
      armR.current.rotation.z = -lift
      armR.current.rotation.x = -0.35
    }
    if (body.current) body.current.position.y = Math.sin(t * 1.6) * 0.012
  })

  const skin = '#7ae8ff'
  const skinDark = '#3aa8d0'

  return (
    <group ref={body} position={[0, 1.05, 0.72]}>
      {/* pelvis / hips */}
      <mesh position={[0, 0.12, 0]}>
        <sphereGeometry args={[0.28, 18, 18]} />
        <meshStandardMaterial color={skinDark} emissive="#1a8cff" emissiveIntensity={0.25} roughness={0.32} metalness={0.12} />
      </mesh>
      {/* torso (basic material so bloom cannot erase the silhouette) */}
      <mesh position={[0, 0.52, 0]}>
        <cylinderGeometry args={[0.34, 0.38, 0.72, 18]} />
        <meshBasicMaterial color={skin} toneMapped={false} />
      </mesh>
      {/* shoulders */}
      <mesh position={[0, 0.88, 0]}>
        <sphereGeometry args={[0.36, 18, 18]} />
        <meshBasicMaterial color={skin} toneMapped={false} />
      </mesh>

      {/* black back panel + white cross + green bars (ref) */}
      <mesh position={[0, 0.55, -0.34]}>
        <boxGeometry args={[0.55, 0.78, 0.07]} />
        <meshStandardMaterial color="#050508" roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.58, -0.39]}>
        <boxGeometry args={[0.11, 0.58, 0.045]} />
        <meshBasicMaterial color="#f4f7ff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.72, -0.39]}>
        <boxGeometry args={[0.3, 0.11, 0.045]} />
        <meshBasicMaterial color="#f4f7ff" toneMapped={false} />
      </mesh>
      <mesh position={[-0.17, 0.55, -0.39]}>
        <boxGeometry args={[0.055, 0.46, 0.04]} />
        <meshBasicMaterial color="#39ff14" toneMapped={false} />
      </mesh>
      <mesh position={[0.17, 0.55, -0.39]}>
        <boxGeometry args={[0.055, 0.46, 0.04]} />
        <meshBasicMaterial color="#39ff14" toneMapped={false} />
      </mesh>

      {/* head */}
      <mesh position={[0, 1.28, 0.02]}>
        <sphereGeometry args={[0.4, 28, 28]} />
        <meshBasicMaterial color="#9af0ff" toneMapped={false} />
      </mesh>
      {/* antenna + yellow bulb */}
      <mesh position={[0, 1.68, 0.02]}>
        <cylinderGeometry args={[0.024, 0.024, 0.28, 8]} />
        <meshBasicMaterial color="#c8f7ff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.86, 0.02]}>
        <sphereGeometry args={[0.06, 12, 12]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      {/* ear / headphone disks */}
      {([-0.38, 0.38] as const).map((x) => (
        <group key={x} position={[x, 1.28, 0.02]} rotation={[0, 0, x > 0 ? -0.12 : 0.12]}>
          <mesh rotation={[0, Math.PI / 2, 0]}>
            <torusGeometry args={[0.14, 0.035, 10, 24]} />
            <meshBasicMaterial color="#39ff14" toneMapped={false} />
          </mesh>
          <mesh position={[x > 0 ? 0.035 : -0.035, 0, 0]}>
            <sphereGeometry args={[0.09, 14, 14]} />
            <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.7} />
          </mesh>
        </group>
      ))}
      {/* arms */}
      <group ref={armL} position={[-0.46, 0.82, 0.05]}>
        <mesh position={[0, -0.36, 0]}>
          <cylinderGeometry args={[0.11, 0.11, 0.78, 12]} />
          <meshBasicMaterial color={skin} toneMapped={false} />
        </mesh>
        <mesh position={[0, -0.8, 0]}>
          <sphereGeometry args={[0.13, 12, 12]} />
          <meshBasicMaterial color="#ffffff" toneMapped={false} />
        </mesh>
      </group>
      <group ref={armR} position={[0.46, 0.82, 0.05]}>
        <mesh position={[0, -0.36, 0]}>
          <cylinderGeometry args={[0.11, 0.11, 0.78, 12]} />
          <meshBasicMaterial color={skin} toneMapped={false} />
        </mesh>
        <mesh position={[0, -0.8, 0]}>
          <sphereGeometry args={[0.13, 12, 12]} />
          <meshBasicMaterial color="#ffffff" toneMapped={false} />
        </mesh>
      </group>
      {/* legs tucked on chair */}
      <mesh position={[-0.16, -0.05, 0.12]} rotation={[0.55, 0, 0.1]}>
        <cylinderGeometry args={[0.1, 0.1, 0.5, 10]} />
        <meshStandardMaterial color={skinDark} />
      </mesh>
      <mesh position={[0.16, -0.05, 0.12]} rotation={[0.55, 0, -0.1]}>
        <cylinderGeometry args={[0.1, 0.1, 0.5, 10]} />
        <meshStandardMaterial color={skinDark} />
      </mesh>
    </group>
  )
}
