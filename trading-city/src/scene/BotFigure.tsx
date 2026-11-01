import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'

/** Simple synthwave humanoid matching the office reference vibe. */
export function BotFigure({ celebrating = false }: { celebrating?: boolean }) {
  const armL = useRef<Group>(null)
  const armR = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const lift = celebrating ? 1.1 : 0.25 + Math.sin(t * 1.4) * 0.08
    if (armL.current) armL.current.rotation.z = lift
    if (armR.current) armR.current.rotation.z = -lift
  })

  return (
    <group position={[0, 0.9, 0.4]}>
      <mesh position={[0, 0.55, 0]}>
        <capsuleGeometry args={[0.28, 0.55, 6, 12]} />
        <meshStandardMaterial color="#5ad0ff" emissive="#1a6cff" emissiveIntensity={0.35} />
      </mesh>
      <mesh position={[0, 1.25, 0]}>
        <sphereGeometry args={[0.32, 20, 20]} />
        <meshStandardMaterial color="#7ae0ff" emissive="#2de2e6" emissiveIntensity={0.25} />
      </mesh>
      {([-0.28, 0.28] as const).map((x) => (
        <mesh key={x} position={[x, 1.28, 0.05]}>
          <sphereGeometry args={[0.08, 12, 12]} />
          <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.2} />
        </mesh>
      ))}
      <group ref={armL} position={[-0.38, 0.75, 0]}>
        <mesh position={[0, -0.28, 0]}>
          <capsuleGeometry args={[0.08, 0.35, 4, 8]} />
          <meshStandardMaterial color="#5ad0ff" />
        </mesh>
      </group>
      <group ref={armR} position={[0.38, 0.75, 0]}>
        <mesh position={[0, -0.28, 0]}>
          <capsuleGeometry args={[0.08, 0.35, 4, 8]} />
          <meshStandardMaterial color="#5ad0ff" />
        </mesh>
      </group>
      <mesh position={[-0.14, 0.05, 0]}>
        <capsuleGeometry args={[0.09, 0.35, 4, 8]} />
        <meshStandardMaterial color="#3a90c0" />
      </mesh>
      <mesh position={[0.14, 0.05, 0]}>
        <capsuleGeometry args={[0.09, 0.35, 4, 8]} />
        <meshStandardMaterial color="#3a90c0" />
      </mesh>
    </group>
  )
}
