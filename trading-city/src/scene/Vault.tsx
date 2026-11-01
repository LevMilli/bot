import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'

export function Vault() {
  const dome = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    if (!dome.current) return
    const t = clock.getElapsedTime()
    const mat = dome.current.material as { emissiveIntensity?: number }
    if (mat.emissiveIntensity != null) mat.emissiveIntensity = 0.45 + Math.sin(t * 1.6) * 0.12
  })

  return (
    <group position={[0, 0, 6]}>
      <mesh ref={dome} position={[0, 1.2, 0]}>
        <sphereGeometry args={[2.4, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial
          color="#1a1630"
          emissive="#f0e6a8"
          emissiveIntensity={0.5}
          metalness={0.4}
          roughness={0.35}
          transparent
          opacity={0.92}
        />
      </mesh>
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[2.5, 48]} />
        <meshStandardMaterial color="#0c0820" emissive="#2de2e6" emissiveIntensity={0.2} />
      </mesh>
      <mesh position={[0, 0.08, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.55, 2.7, 48]} />
        <meshBasicMaterial color="#f9c80e" transparent opacity={0.7} />
      </mesh>
    </group>
  )
}
