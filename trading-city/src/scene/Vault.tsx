import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'

function Crystal({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh>
        <coneGeometry args={[0.18, 0.7, 4]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.75} />
      </mesh>
      <mesh position={[0, -0.28, 0]}>
        <cylinderGeometry args={[0.05, 0.05, 0.2, 6]} />
        <meshBasicMaterial color="#0a4a66" />
      </mesh>
    </group>
  )
}

export function Vault() {
  const dome = useRef<Mesh>(null)
  const glow = useRef<Mesh>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const pulse = 0.55 + Math.sin(t * 1.5) * 0.18
    if (dome.current) {
      const mat = dome.current.material as { emissiveIntensity?: number }
      if (mat.emissiveIntensity != null) mat.emissiveIntensity = pulse
    }
    if (glow.current) {
      const s = 1 + Math.sin(t * 1.5) * 0.04
      glow.current.scale.set(s, s, s)
    }
  })

  const crystals: [number, number, number][] = [
    [-3.1, 0.45, -0.4],
    [-2.5, 0.45, 1.6],
    [2.6, 0.45, 1.5],
    [3.2, 0.45, -0.3],
    [-3.4, 0.45, 0.7],
    [3.4, 0.45, 0.6],
  ]

  return (
    <group position={[0, 0, 5.2]}>
      <mesh ref={dome} position={[0, 0.02, 0]} scale={[1, 1.35, 1]}>
        <sphereGeometry args={[2.55, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial
          color="#e8e0c0"
          emissive="#fff6c8"
          emissiveIntensity={0.85}
          metalness={0.45}
          roughness={0.18}
          transparent
          opacity={0.97}
        />
      </mesh>
      <mesh ref={glow} position={[0, 0.02, 0]} scale={[1, 1.35, 1]}>
        <sphereGeometry args={[2.75, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshBasicMaterial color="#ffe9a0" transparent opacity={0.22} depthWrite={false} />
      </mesh>
      <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[2.65, 48]} />
        <meshStandardMaterial color="#0a0820" emissive="#2de2e6" emissiveIntensity={0.4} />
      </mesh>
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.7, 2.95, 64]} />
        <meshBasicMaterial color="#f9c80e" transparent opacity={0.9} />
      </mesh>
      <pointLight position={[0, 2.4, 0]} intensity={2.4} color="#fff0b0" distance={18} />
      {crystals.map((p, i) => (
        <Crystal key={i} position={p} />
      ))}
    </group>
  )
}
